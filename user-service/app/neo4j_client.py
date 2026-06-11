import importlib
from dataclasses import dataclass

from django.conf import settings


@dataclass
class BehaviorEvent:
	user_id: int
	product_id: int
	action: str
	event_time: str


class Neo4jBehaviorClient:
	def __init__(self):
		self._driver = None
		self._initialized = False

	def _init_driver(self):
		if self._initialized:
			return
		self._initialized = True

		if not getattr(settings, 'NEO4J_ENABLED', False):
			return

		try:
			neo4j_module = importlib.import_module('neo4j')
			graph_database = neo4j_module.GraphDatabase
			self._driver = graph_database.driver(
				settings.NEO4J_URI,
				auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
			)
		except Exception:
			self._driver = None

	def save_behavior(self, event: BehaviorEvent):
		self._init_driver()
		if self._driver is None:
			raise RuntimeError('Neo4j is not available. Check NEO4J settings and neo4j package.')

		query = """
		MERGE (u:User {id: $user_id})
		SET u.updated_at = datetime(),
			u.last_behavior_at = datetime($event_time)
		MERGE (p:Product {id: $product_id})
		SET p.updated_at = datetime(),
			p.last_behavior_at = datetime($event_time)
		FOREACH(_ IN CASE WHEN $action = 'view' THEN [1] ELSE [] END |
			MERGE (u)-[r:VIEW]->(p)
			SET r.event_count = coalesce(r.event_count, 0) + 1,
				r.last_action = $action,
				r.last_event_at = datetime($event_time),
				r.updated_at = datetime()
		)
		FOREACH(_ IN CASE WHEN $action = 'add_to_cart' THEN [1] ELSE [] END |
			MERGE (u)-[r:ADD_TO_CART]->(p)
			SET r.event_count = coalesce(r.event_count, 0) + 1,
				r.last_action = $action,
				r.last_event_at = datetime($event_time),
				r.updated_at = datetime()
		)
		FOREACH(_ IN CASE WHEN $action = 'buy' THEN [1] ELSE [] END |
			MERGE (u)-[r:BUY]->(p)
			SET r.event_count = coalesce(r.event_count, 0) + 1,
				r.last_action = $action,
				r.last_event_at = datetime($event_time),
				r.updated_at = datetime()
		)
		FOREACH(_ IN CASE WHEN $action = 'rating' THEN [1] ELSE [] END |
			MERGE (u)-[r:RATING]->(p)
			SET r.event_count = coalesce(r.event_count, 0) + 1,
				r.last_action = $action,
				r.last_event_at = datetime($event_time),
				r.updated_at = datetime()
		)
		FOREACH(_ IN CASE WHEN $action = 'search' THEN [1] ELSE [] END |
			MERGE (u)-[r:SEARCH]->(p)
			SET r.event_count = coalesce(r.event_count, 0) + 1,
				r.last_action = $action,
				r.last_event_at = datetime($event_time),
				r.updated_at = datetime()
		)
		"""

		with self._driver.session() as session:
			session.run(
				query,
				user_id=event.user_id,
				product_id=event.product_id,
				action=event.action,
				event_time=event.event_time,
			)


neo4j_behavior_client = Neo4jBehaviorClient()
