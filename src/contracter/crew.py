import os
import yaml
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase
from langchain_groq import ChatGroq
from contracter.tools.read_email_tool import GmailTool
from contracter.tools.google_docs_tool import GoogleDocsTool
from contracter.tools.rag_tool import RAGModel
from langchain_google_genai import ChatGoogleGenerativeAI 

gemini = ChatGoogleGenerativeAI(model="gemini-pro",
                                verbose=True,
                                temperature=0.5,
                                google_api_key="AIzaSyANgglqkPCxFu9Kp0x4zZXead4IDF0F48I")

llama = ChatGroq(
    api_key="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",
    model="llama3-70b-8192",
    max_tokens=8192
)

llama3_1 = ChatGroq(
    api_key="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",
    model="llama-3.1-70b-versatile",
    max_tokens=8000
)
@CrewBase
class ContracterCrew:
    """Contracter crew"""
    agents_config_file = 'src/contracter/config/agents.yaml'
    tasks_config_file = 'src/contracter/config/tasks.yaml'

    def __init__(self):
        self.gmail_tool = GmailTool()
        self.google_docs_tool = GoogleDocsTool()
        self.rag_tool = RAGModel()
        self.latest_email_content = None
        self.email_summary = None
        self.agents = []
        self.tasks = []
        self.google_doc_id = None
        self.query = None
        self.rag_results = None

        with open(self.agents_config_file, 'r') as file:
            self.agents_config = yaml.safe_load(file)

        with open(self.tasks_config_file, 'r') as file:
            self.tasks_config = yaml.safe_load(file)

    def fetch_email_content(self):
        self.gmail_tool.authenticate_gmail()
        latest_email = self.gmail_tool.get_latest_email()
        self.latest_email_content = latest_email['body'] if latest_email else "No content available."

    def fetch_rag_content(self):
        if self.rag_tool.embeddings is None:
            self.rag_tool.load_embeddings(r'src/contracter/text_chunks_embeddings_df.csv')
        if self.query:
            self.rag_results = self.rag_tool.top_results(self.query)

    def generate_query_from_email(self):
        if self.latest_email_content:
            prompt = f"Extract a query from the following email: {self.latest_email_content}"
            response = llama3_1.invoke(prompt)
            self.query = response.text.strip() if hasattr(response, 'text') else str(response).strip()

    def initialize_agents(self):
        self.mail_reader = Agent(
            config=self.agents_config['Mail_Reader'],
            tool=[self.gmail_tool],
            allow_delegation=False,
            verbose=True,
            llm=llama3_1
        )

        self.contract_agent = Agent(
            config=self.agents_config['Contract_Agent'],
            tool=[self.gmail_tool, self.google_docs_tool, self.rag_tool],
            allow_delegation=False,
            verbose=True,
            llm=llama3_1
        )

        self.agents.extend([self.mail_reader, self.contract_agent])

    def initialize_tasks(self):
        email_content = self.latest_email_content if self.latest_email_content else "No content available."

        self.email_extraction_task = Task(
            description=f"Extract relevant contract details from the provided {email_content}.",
            expected_output="A comprehensive summary of the email, detailing all necessary information for the contract. This includes specifics about the parties, the scope of work, pricing, timelines, and any special conditions.",
            agent=self.mail_reader
        )

        self.create_complete_contract_task = Task(
            description="Using the email summary provided by Mail_Reader and insights from the RAG model, create and write a complete contract.",
            expected_output="A fully written contract in a Google Doc, including title, offer, acceptance, awareness, consideration, capacity, legality, and review sections. The document should be free from placeholders, redundancies, and irrelevant content, and should be formatted professionally.",
            agent=self.contract_agent
        )

        self.tasks.extend([self.email_extraction_task, self.create_complete_contract_task])

    def crew(self) -> Crew:
        """Creates the Contracter crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=2
        )

    def kickoff(self):
        self.fetch_email_content()
        self.generate_query_from_email()
        self.fetch_rag_content()
        self.initialize_agents()
        self.initialize_tasks()
        self.google_docs_tool.authenticate_google_docs()
        self.google_doc_id = self.google_docs_tool.create_document("Sihame Contract")

        crew_instance = self.crew()
        crew_output = crew_instance.kickoff()

        final_content = self.organize_contract(crew_output.tasks_output)
        self.google_docs_tool.write_to_document(document_id=self.google_doc_id, content=final_content)

    def organize_contract(self, tasks_output):
        final_content = []
        for task_output in tasks_output:
            final_content.append(task_output.raw)
        return "\n\n".join(final_content)

if __name__ == '__main__':
    ContracterCrew().kickoff()
