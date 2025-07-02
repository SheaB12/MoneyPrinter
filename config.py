"""API credential configuration.

Credentials are loaded from environment variables so secrets are not stored
in the repository. Ensure the following variables are set before running the
application:

```
TRADIER_TOKEN         - Tradier API token
TRADIER_ACCOUNT_ID    - Tradier account ID
OPENAI_API_KEY        - OpenAI API key
```
"""

import os

TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

missing = [name for name, val in {
    "TRADIER_TOKEN": TRADIER_TOKEN,
    "TRADIER_ACCOUNT_ID": ACCOUNT_ID,
    "OPENAI_API_KEY": OPENAI_API_KEY,
}.items() if not val]

if missing:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(missing)}"
    )

