"""List which Claude models this AWS account can call on Bedrock (one tiny request each)."""
from dotenv import load_dotenv
load_dotenv()
import os
import anthropic
from anthropic import AnthropicBedrockMantle

client = AnthropicBedrockMantle(aws_region=os.environ["AWS_REGION"])
for model in ["anthropic.claude-opus-5-5", "anthropic.claude-sonnet-5-5", "anthropic.claude-haiku-5-5",
              "anthropic.claude-opus-5", "anthropic.claude-opus-4-8", "anthropic.claude-sonnet-5",
              "anthropic.claude-haiku-4-5"]:
    try:
        r = client.messages.create(model=model, max_tokens=50, messages=[{"role": "user", "content": "Say ok"}])
        print(model, "OK")
    except anthropic.APIStatusError as e:
        print(model, e.status_code, str(e.message)[:110])
