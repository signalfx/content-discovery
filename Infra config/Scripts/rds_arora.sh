
#!/bin/bash

#mysql -h bits-arrora-mysql.cluster-cdw6johvs3ne.us-west-1.rds.amazonaws.com -u admin -***** -e "CREATE DATABASE IF NOT EXISTS prod;"
#mysql -h bits-arrora-mysql.cluster-cdw6johvs3ne.us-west-1.rds.amazonaws.com -u admin -***** -D prod -e "CREATE TABLE products (product_name nvarchar(50), price int);"
#mysql -h bits-arrora-mysql.cluster-cdw6johvs3ne.us-west-1.rds.amazonaws.com -u admin -***** -D prod -e "INSERT INTO products (product_name, price) VALUES ('Desktop Computer',800),('Laptop',1200),('Tablet',200),('Monitor',350),('Printer',150);"
mysql -h bits-arrora-mysql.cluster-ro-cdw6johvs3ne.us-west-1.rds.amazonaws.com -u admin -******* -D prod -e "SELECT * FROM products;"