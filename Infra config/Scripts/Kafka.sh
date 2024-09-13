# Configuration
BOOTSTRAP_SERVER="localhost:9093"
KAFKA_OPTS="-Djava.security.auth.login.config=/home/ubuntu/kafka2/config/kafka_server_jaas.conf"
TOPIC1="xyz1"
TOPIC2="xyz2"
TOPIC3="xyz3"

# Export the Kafka options
export KAFKA_OPTS

# Function to delete multiple topics
delete_topics() {
    echo "Deleting topics..."
    for TOPIC in "$TOPIC1" "$TOPIC2" "$TOPIC3"; do
        if bin/kafka-topics.sh --list --bootstrap-server $BOOTSTRAP_SERVER --command-config config/producer.properties | grep -q "^$TOPIC$"; then
            bin/kafka-topics.sh --delete --topic "$TOPIC" --bootstrap-server $BOOTSTRAP_SERVER --command-config config/producer.properties
            echo "Deletion of topic $TOPIC initiated."
        else
            echo "Topic $TOPIC does not exist. Skipping deletion."
        fi
    done
    echo "Topics deletion initiated."

    # Wait for a few seconds to ensure topics are deleted
    sleep 10
}

# Function to create multiple topics
create_topics() {
    echo "Creating topics..."
    for TOPIC in "$TOPIC1" "$TOPIC2" "$TOPIC3"; do
        if ! bin/kafka-topics.sh --list --bootstrap-server $BOOTSTRAP_SERVER --command-config config/producer.properties | grep -q "^$TOPIC$"; then
            echo "Creating topic $TOPIC..."
            if bin/kafka-topics.sh --create --topic "$TOPIC" --partitions 1 --replication-factor 1 --bootstrap-server $BOOTSTRAP_SERVER --command-config config/producer.properties; then
                echo "Topic $TOPIC created."
            else
                echo "Failed to create topic $TOPIC."
                exit 1
            fi
        else
            echo "Topic $TOPIC already exists."
        fi
    done
    echo "Topics creation check complete."
}

# Function to send multiple messages
send_messages() {
    echo "Sending messages..."
    echo "Message for THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL,>
    echo "Message for THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL,>
    echo "Message for Message for THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR >
    echo "Messages sent."

    # Wait for a few seconds to ensure messages are sent and processed
    sleep 5
}
