#!/bin/bash

export PGPASSWORD=<your_password>

psql -U postgres -d example -c 'CREATE TABLE COMPANY(ID INT PRIMARY KEY NOT NULL, NAME TEXT NOT NULL, AGE INT NOT NULL, ADDRESS CHAR(50), SALARY REAL, JOIN_DATE DATE);'
for i in {1..100}; do psql -U postgres -d example -c "INSERT INTO COMPANY (ID,NAME,AGE,ADDRESS,SALARY,JOIN_DATE) VALUES ($i, 'Paul', 32, 'California', 20000.00,'2001-07-13');"; done
sleep 1m
for i in {1..40}; do psql -U postgres -d example -c "UPDATE COMPANY SET AGE = 15 WHERE ID = $i;"; done
sleep 1m
psql -U postgres -d example -c 'commit;'
sleep 1m
for i in {1..100}; do psql -U postgres -d example -c "DELETE FROM COMPANY WHERE ID = $i;"; done
sleep 1m
psql -U postgres -d example -c 'ROLLBACK;'
sleep 1m
psql -U postgres -d example -c 'DROP TABLE COMPANY;'