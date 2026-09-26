export type AwsCredentials = { accessKeyId: string; secretAccessKey: string; sessionToken?: string };

type Signing = { url: string; body: string; region: string; service: string; amzDate: string };

const encoder = new TextEncoder();

function hex(bytes: ArrayBuffer): string {
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(text: string): Promise<string> {
  return hex(await crypto.subtle.digest("SHA-256", encoder.encode(text)));
}

async function hmac(key: ArrayBuffer | Uint8Array, data: string): Promise<ArrayBuffer> {
  const imported = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return crypto.subtle.sign("HMAC", imported, encoder.encode(data));
}

export function amzDate(now: Date): string {
  return now.toISOString().replace(/[:-]|\.\d{3}/g, "");
}

export async function signedPostHeaders(credentials: AwsCredentials, signing: Signing): Promise<Record<string, string>> {
  const url = new URL(signing.url);
  const headers: Record<string, string> = {
    "content-type": "application/json",
    host: url.host,
    "x-amz-date": signing.amzDate,
    ...(credentials.sessionToken ? { "x-amz-security-token": credentials.sessionToken } : {}),
  };
  const names = Object.keys(headers).sort();
  const canonical = [
    "POST",
    url.pathname,
    "",
    names.map((name) => `${name}:${headers[name]}\n`).join(""),
    names.join(";"),
    await sha256(signing.body),
  ].join("\n");
  const day = signing.amzDate.slice(0, 8);
  const scope = `${day}/${signing.region}/${signing.service}/aws4_request`;
  const toSign = ["AWS4-HMAC-SHA256", signing.amzDate, scope, await sha256(canonical)].join("\n");
  let key = await hmac(encoder.encode(`AWS4${credentials.secretAccessKey}`), day);
  for (const part of [signing.region, signing.service, "aws4_request"]) key = await hmac(key, part);
  const signature = hex(await hmac(key, toSign));
  const authorization = `AWS4-HMAC-SHA256 Credential=${credentials.accessKeyId}/${scope}, SignedHeaders=${names.join(";")}, Signature=${signature}`;
  return { ...headers, authorization };
}
