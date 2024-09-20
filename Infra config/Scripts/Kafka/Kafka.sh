
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
    echo "Message for THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.Readme $TOPIC1" | bin/kafka-console-producer.sh --topic "$TOPIC1" --bootstrap-server $BOOTSTRAP_SERVER --producer.config config/producer.properties
    echo "Message for THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.Readme $TOPIC2" | bin/kafka-console-producer.sh --topic "$TOPIC2" --bootstrap-server $BOOTSTRAP_SERVER --producer.config config/producer.properties
    echo "Message for Message for THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.Readme $TOPIC3" | bin/kafka-console-producer.sh --topic "$TOPIC3" --bootstrap-server $BOOTSTRAP_SERVER --producer.config config/producer.properties
    echo "Messages sent."

    # Wait for a few seconds to ensure messages are sent and processed
    sleep 5
}

# Function to read messages from a topic
read_messages() {
    for TOPIC in "$TOPIC1" "$TOPIC2" "$TOPIC3"; do
        echo "Reading messages from $TOPIC..."
        bin/kafka-console-consumer.sh --topic "$TOPIC" --bootstrap-server $BOOTSTRAP_SERVER --from-beginning --max-messages 10 --consumer.config config/consumer.properties --timeout-ms 5000
    done
}

# Run the functions
delete_topics
create_topics
send_messages
read_messages
delete_topics

echo "Kafka operations completed."