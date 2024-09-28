import os
import pandas as pd
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util
from spacy.lang.en import English

class RAGModel:
    def __init__(self, embedding_model_name="sentence-transformers/all-distilroberta-v1"):
        self.embedding_model_name = embedding_model_name
        self.nlp = English()
        self.nlp.add_pipe("sentencizer")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(self.embedding_model_name, device=self.device)
        self.embeddings = None
        self.pages_and_chunks = None

    def parse_embedding(self, embedding_str):
        try:
            embedding_str = embedding_str.strip("[]")
            embedding_values = [float(x) for x in embedding_str.split() if x]
            return np.array(embedding_values)
        except ValueError:
            return np.array([])

    def load_embeddings(self, csv_path):
        data_embeddings = pd.read_csv(csv_path)
        data_embeddings['embedding'] = data_embeddings['embedding'].apply(self.parse_embedding)

        correct_dim = 768
        data_embeddings = data_embeddings[data_embeddings['embedding'].map(lambda x: len(x) == correct_dim)]

        if data_embeddings.empty:
            raise ValueError("No valid embeddings found in the CSV file.")

        self.pages_and_chunks = data_embeddings.to_dict(orient="records")
        self.embeddings = torch.tensor(np.stack(data_embeddings['embedding'].tolist(), axis=0), dtype=torch.float32).to(self.device)

    def retrieve(self, query, num_resources_to_return=5):
        query_embedding = self.model.encode(query, convert_to_tensor=True).to(self.device)
        dot_score = util.dot_score(query_embedding, self.embeddings)[0]
        scores, indices = torch.topk(dot_score, k=num_resources_to_return)
        return scores, indices

    def print_wrapped(self, text, wrap_length=80):
        import textwrap
        wrapped_text = textwrap.fill(text, wrap_length)
        return wrapped_text

    def top_results(self, query, num_resources_to_return=10):
        scores, indices = self.retrieve(query=query, num_resources_to_return=num_resources_to_return)
        texts = []
        for score, idx in zip(scores, indices):
            text = self.print_wrapped(self.pages_and_chunks[idx]["sentences_chunks"])
            texts.append(text)
        return texts
