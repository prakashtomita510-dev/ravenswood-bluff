from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8045/v1",
    api_key="sk-877a04a99eb541b9b570f03eee14c6a5"
)

try:
    response = client.chat.completions.create(
        model="gemini-3-flash",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("API Response:", response.choices[0].message.content)
except Exception as e:
    print("API Error:", e)
