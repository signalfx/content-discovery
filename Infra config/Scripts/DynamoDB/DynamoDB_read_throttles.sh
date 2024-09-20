# 2. Table Name
TABLE_NAME=bits_metrics
# 3. Function to Retry Reads with Exponential Backoff
read_with_throttle() {
  local retries=5
  local max_delay=30
  while true; do
    aws dynamodb scan --table-name $TABLE_NAME || {
      if [[ $retries -gt 0 ]]; then
        sleep $((RANDOM % max_delay))  # Random delay within range
        retries=$((retries - 1))
        max_delay=$((max_delay * 2))  # Exponential backoff
        echo "Read throttled, retrying in $max_delay seconds..."
      else
        echo "Read failed after retries, exiting..."
        exit 1
      fi
    }
    return 0  # Successful read
  done
}
# 4. Perform Read with Throttle Handling
read_with_throttle
echo "Read completed successfully!"