"""One tiny request to check Bedrock access before running the agent."""
from dotenv import load_dotenv
load_dotenv()
import os
from anthropic import AnthropicBedrockMantle

client = AnthropicBedrockMantle(aws_region=os.environ["AWS_REGION"])
msg = client.messages.create(
    model=os.environ["MODEL_ID"],
    max_tokens=200,
    messages=[{"role": "user", "content": "Reply with the single word: ready"}],
)
print(msg.model, msg.stop_reason, [b.text for b in msg.content if b.type == "text"], msg.usage.input_tokens, msg.usage.output_tokens)
