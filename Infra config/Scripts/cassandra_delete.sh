echo "changing dir"
cqlsh 127.0.0.1 -u cassandra -p cassandra -e "DROP TABLE IF EXISTS catalog"
echo "Table deleted"