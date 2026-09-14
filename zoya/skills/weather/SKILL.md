---
name: weather
description: Today's live weather for a city — temperature, conditions, high and low, rain chance.
metadata:
  tools: [get_weather, memory_search]
  triggers:
    - action: get_weather
      pattern: '^(?:what(?:''s| is)\s+)?(?:the\s+)?weather(?:\s+like)?(?:\s+today)?\s+(?:in|for|at)\s+(?P<city>[a-z .-]+?)(?:\s+today)?$'
    - action: get_weather
      pattern: '^(?:how(?:''s| is)\s+the\s+weather|is it (?:going to )?rain(?:ing)?)\s+in\s+(?P<city>[a-z .-]+?)(?:\s+today)?$'
---
# Weather

Say the city and country the tool used. With no city, `memory_search("home city")`, else ask.
