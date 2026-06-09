from langchain_core.prompts import PromptTemplate

chat_prompt=PromptTemplate.from_template(
    """
    You are a helpful educational assistant.
    Answer the question using ONLY the context below.

    Question:
    {question}

    Context:
    {context}

    If relevant, mention the document source.

    """
)

quiz_prompt=PromptTemplate.from_template(
    """
    You are a test-generating assistant.
    Using the context below, generate {num_questions}
    multiple-choice questions.

    Format STRICTLY as:

    Question 1: ...
    A) ...
    B) ...
    C) ...
    Correct Answer: A

    Context:
    {context}
    """
)