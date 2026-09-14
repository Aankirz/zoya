"""Share a file Zoya made (STACK §9 tier 2): private S3 object → pre-signed GET link → SNS email.

"Send it to my sister" is a SEND (D61): `share_file` asks the user out loud inside the action
(safety.require_confirmation), rebuilding the summary right before it acts. Only files under
~/Documents/Zoya/ can be shared, so injected text can't send ~/.ssh anywhere (§12.2).

Recipients are names, never addresses: each contact is one email subscription on SHARE_TOPIC_ARN
with a filter policy {"recipient": ["sister"]}, and the publish carries that message attribute
(https://docs.aws.amazon.com/sns/latest/dg/sns-message-filtering.html). A name without a confirmed
subscription is refused; Zoya never guesses an address. Test mode (SHARE_TEST_ENV=1) sends to the
owner's own zoya-alerts subscription and says so.

Objects stay private; the link is SigV4 pre-signed for SHARE_LINK_TTL_S
(https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html,
https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html).
Only the zoya-app policy (D49) is needed: s3:PutObject/GetObject on zoya-*/*, sns:Publish on zoya-*.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path

from strands import tool

from zoya import aws, safety
from zoya.config import (
    ALERTS_TOPIC_ARN,
    S3_UPLOAD_TIMEOUT_S,
    SHARE_BUCKET,
    SHARE_CONTACTS,
    SHARE_LINK_TTL_S,
    SHARE_PREFIX,
    SHARE_TEST_ENV,
    SHARE_TOPIC_ARN,
    aws_region,
)
from zoya.tools import ToolError
from zoya.tools.office import zoya_file

log = logging.getLogger(__name__)
SECONDS_PER_MINUTE = 60
MS_PER_S = 1000


def recipient_route(recipient: str) -> tuple[str, dict, str]:
    """(topic, message attributes, spoken name). Parser (tested): unknown names are refused."""
    name = " ".join(recipient.lower().replace("my ", " ").split())
    if os.environ.get(SHARE_TEST_ENV) == "1":
        return ALERTS_TOPIC_ARN, {}, "your own email, as a test"
    if name not in SHARE_CONTACTS:
        raise ToolError(
            f"I don't have an email for your {name or 'contact'} yet, so I didn't send anything."
        )
    return (
        SHARE_TOPIC_ARN,
        {"recipient": {"DataType": "String", "StringValue": name}},
        f"your {name}",
    )


def _s3() -> object:
    import boto3
    from botocore.config import Config

    profile = os.environ.get("AWS_PROFILE")
    if not profile:
        raise ToolError("Sharing needs AWS, which is off right now.")
    config = Config(
        signature_version="s3v4",
        connect_timeout=S3_UPLOAD_TIMEOUT_S,
        read_timeout=S3_UPLOAD_TIMEOUT_S,
        retries={"max_attempts": 1},
    )
    session = boto3.Session(profile_name=profile)
    return aws.traced(session.client("s3", region_name=aws_region(), config=config))


@tool
def share_file(path: str, recipient: str) -> str:
    """Email a private download link to a file Zoya made. Zoya asks the user to confirm first.

    Args:
        path: Full path of a file in ~/Documents/Zoya/.
        recipient: Who gets it, as the user said it, e.g. "sister".
    """
    file = zoya_file(path)
    topic, attributes, spoken = recipient_route(recipient)
    action = safety.Action("send", f"email a link to {file.name}", target=spoken)

    def live() -> safety.Action:
        zoya_file(str(file))  # still there, still Zoya's
        return safety.Action(
            "send", f"email a link to {file.name}", target=recipient_route(recipient)[2]
        )

    safety.require_confirmation(action, current=live)
    started = time.monotonic()
    link = _upload(file)
    _publish(topic, attributes, file.name, link)
    safety.log_safety_timing(
        event="share_file", share_ms=round((time.monotonic() - started) * MS_PER_S)
    )
    minutes = SHARE_LINK_TTL_S // SECONDS_PER_MINUTE
    return f"Sent {spoken} a link to {file.name}. It works for {minutes} minutes."


def _upload(file: Path) -> str:
    key = f"{SHARE_PREFIX}{uuid.uuid4().hex}/{file.name}"
    s3 = _s3()
    try:
        s3.upload_file(str(file), SHARE_BUCKET, key)
        return s3.generate_presigned_url(
            "get_object", Params={"Bucket": SHARE_BUCKET, "Key": key}, ExpiresIn=SHARE_LINK_TTL_S
        )
    except Exception as error:  # noqa: BLE001 — AWS errors become a spoken reason
        log.warning("share upload failed (%s)", aws._reason(error))
        raise ToolError("I couldn't upload the file, so nothing was sent.") from error


def _publish(topic: str, attributes: dict, name: str, link: str) -> None:
    sns = aws.client("sns")
    if sns is None:
        raise ToolError("Sharing needs AWS, which is off right now. Nothing was sent.")
    minutes = SHARE_LINK_TTL_S // SECONDS_PER_MINUTE
    try:
        sns.publish(
            TopicArn=topic,
            Subject=f"Zoya shared a file with you: {name}"[:100],  # SNS subject limit
            Message=f"A file was shared with you: {name}\n\nDownload (works for {minutes} "
            f"minutes):\n{link}\n",
            MessageAttributes=attributes,
        )
    except Exception as error:  # noqa: BLE001
        log.warning("share email failed (%s)", aws._reason(error))
        raise ToolError(
            "The file uploaded but the email didn't go out. Nothing was sent."
        ) from error
