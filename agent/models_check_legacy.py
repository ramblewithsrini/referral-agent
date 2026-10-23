"""Check the legacy Bedrock route (InvokeModel, ARN-versioned EU inference profiles)."""
from dotenv import load_dotenv
load_dotenv()
import os
import anthropic
from anthropic import AnthropicBedrock

client = AnthropicBedrock(aws_region=os.environ["AWS_REGION"])
for model in ["eu.anthropic.claude-opus-4-6-v1", "eu.anthropic.claude-sonnet-4-6",
              "eu.anthropic.claude-haiku-4-5-20251001-v1:0"]:
    try:
        r = client.messages.create(model=model, max_tokens=50, messages=[{"role": "user", "content": "Say ok"}])
        print(model, "OK", [b.text for b in r.content if b.type == "text"])
    except anthropic.APIStatusError as e:
        print(model, e.status_code, str(e.message)[:160])
