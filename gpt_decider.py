import openai
import json
from config import OPENAI_API_KEY

# Use the newer OpenAI client interface
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def gpt_decision(df):
    candles = df.tail(30)
    formatted = "\n".join(
        f"{i}: O={float(row['Open']):.2f}, H={float(row['High']):.2f}, "
        f"L={float(row['Low']):.2f}, C={float(row['Close']):.2f}, V={int(row['Volume'])}"
        for i, row in candles.iterrows()
    )

    prompt = (
        "You are an elite SPY options day trader.\n"
        "Analyze the last 30 minutes of 1-minute SPY candles. Based on this:\n"
        "- Detect trends, reversals, breakouts, or pullbacks.\n"
        "- Consider volume and momentum.\n"
        "- Be strict — only CALL or PUT if it's a clear edge. Otherwise SKIP.\n\n"
        "Return a JSON response in the following format:\n"
        "{\n"
        '  "decision": "call" | "put" | "skip",\n'
        '  "confidence": 0-100,\n'
        '  "reason": "one-line summary of logic",\n'
        '  "stop_loss_pct": integer (e.g. 25 for 25%),\n'
        '  "target_pct": integer (e.g. 60 for 60%)\n'
        "}\n\n"
        "Here are the recent SPY candles:\n"
        f"{formatted}\n\n"
        "Respond ONLY with the JSON block."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content
        data = json.loads(reply)

        return (
            data.get("decision", "skip").lower(),
            int(data.get("confidence", 0)),
            data.get("reason", "No reason given."),
            int(data.get("stop_loss_pct", 25)),
            int(data.get("target_pct", 60))
        )
    except Exception as e:
        print("OpenAI Error:", e)
        return "skip", 0, "error", 25, 60
