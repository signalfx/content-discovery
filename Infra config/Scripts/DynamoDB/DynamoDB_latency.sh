
# Set your AWS region and DynamoDB table name
AWS_REGION="us-west-1"
DYNAMODB_TABLE="bits_metrics"

# Number of read operations to perform
NUM_READS=10000

for ((i=1; i<=$NUM_READS; i++)); do
  # Perform a read operation on DynamoDB
  aws dynamodb get-item \
    --region $AWS_REGION \
    --table-name $DYNAMODB_TABLE \
    --key '{"id": {"S": "id"}}'

  # Check the exit status of the previous command
  if [ $? -eq 0 ]; then
    echo "Read operation $i successful"
  else
    echo "Read operation $i throttled"
  fi

  # Sleep for a short duration to avoid overwhelming DynamoDB
  sleep 1
done

echo "Read operations completed"