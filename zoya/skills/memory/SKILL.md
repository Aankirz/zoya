---
name: memory
description: Remember facts about the user (usual groceries, brands, addresses, contacts, corrections) and look them up.
metadata:
  tools: [memory_add, memory_search]
  triggers:
    - action: memory_add
      pattern: '^(?:please\s+)?(?:remember|keep in mind|don''t forget)\s+(?:that\s+)?(?P<content>(?:my|i|i''m|i am|our|mera|meri|mere|hamara)\b.+)$'
    - action: memory_search
      pattern: '^what (?:do you remember|do you know) about\s+(?P<query>.+)$'
---
# Memory

Save one fact per memory_add call, in the user's words. Never passwords, OTPs or card numbers: the
tool refuses them, so tell the user you can't store that. Corrections ("no, I meant Rahul Verma")
use category correction.
