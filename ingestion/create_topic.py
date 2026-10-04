import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC

admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
try:
    admin.create_topics([NewTopic(KAFKA_TOPIC, num_partitions=3, replication_factor=1)])
    print("topic created")
except TopicAlreadyExistsError:
    print("topic already exists")
finally:
    admin.close()