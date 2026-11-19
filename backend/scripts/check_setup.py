import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI 

for key in ("OPENAI_API_KEY", "OPENAI_MODEL", "LANGSMITH_API_KEY"):
    if not os.getenv(key):
        raise SystemExit(f"Missing {key} in backend/.env")

llm = ChatOpenAI(model=os.environ["OPENAI_MODEL"])
reply = llm.invoke("What is Property Management? ")

print("Model reply:", reply.content)
print("LangSmith project:", os.getenv("LANGSMITH_PROJECT"))
print("Now open smith.langchain.com and find this run in that project.")