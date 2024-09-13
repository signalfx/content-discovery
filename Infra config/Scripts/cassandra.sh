cqlsh 127.0.0.1 -u cassandra -p cassandra -e "CREATE KEYSPACE IF NOT EXISTS catalog WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};"
cqlsh 127.0.0.1 -u cassandra -p cassandra -e "USE catalog; CREATE TABLE IF NOT EXISTS clothes (item_id UUID PRIMARY KEY, category TEXT, brand TEXT, size TEXT, color TEXT, price DECIMAL, quantity INT);"
cqlsh 127.0.0.1 -u cassandra -p cassandra -e "
USE catalog;
INSERT INTO clothes (item_id, category, brand, size, color, price, quantity)
VALUES
   (uuid(), 'T-shirt', 'ExampleBrand', 'M', 'Blue', 19.99, 50);"
cqlsh 127.0.0.1 -u cassandra -p cassandra -e "USE catalog; SELECT * FROM clothes;"