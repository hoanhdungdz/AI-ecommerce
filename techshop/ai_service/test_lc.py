from langchain_openai import OpenAIEmbeddings, ChatOpenAI
try:
    print("Testing OpenAIEmbeddings with openai_api_key")
    em = OpenAIEmbeddings(openai_api_key="sk-12345")
    print("Success")
except Exception as e:
    print(repr(e))

try:
    print("Testing OpenAIEmbeddings with api_key")
    em = OpenAIEmbeddings(api_key="sk-12345")
    print("Success")
except Exception as e:
    print(repr(e))

try:
    print("Testing ChatOpenAI with openai_api_key")
    llm = ChatOpenAI(openai_api_key="sk-12345")
    print("Success")
except Exception as e:
    print(repr(e))

try:
    print("Testing ChatOpenAI with api_key")
    llm = ChatOpenAI(api_key="sk-12345")
    print("Success")
except Exception as e:
    print(repr(e))
