from .services import HybridRecommender, KnowledgeGraphService, LSTMTrainerTF, RAGService


class ServiceContainer:
    def __init__(self) -> None:
        self.lstm = LSTMTrainerTF()
        self.graph = KnowledgeGraphService()
        self.rag = RAGService()
        self.hybrid = HybridRecommender()


container = ServiceContainer()
