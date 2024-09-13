Solr is highly reliable, scalable and fault tolerant, providing distributed indexing, replication and load-balanced querying, automated failover and recovery, centralized configuration and more. Solr powers the search and navigation features of many of the world’s largest internet sites.

Let’s get started with installations.

1. Keep the server up-to-date
> yum update -y

2. Install all required packages:
> yum install java lsof mysql-connector-java

3. Now, download and install Apache Solr
You can check the latest version of Apache Solr here:

https://lucene.apache.org/solr/downloads.html

For download link, you can click on the version you want to download and install. Also you can find the commands to verify the integrity of the files on the same download page. It’s always recommended to verify the gpg.

Follow these steps to install Apache Solr 8.5.2

> wget https://mirrors.estointernet.in/apache/lucene/solr/8.5.2/solr-8.5.2.tgz
> tar xzf solr-8.5.2.tgz solr-8.5.2/bin/install_solr_service.sh –strip-components=2

The bin/solr script makes it easy to get started with SolrCloud as it walks you through the process of launching Solr nodes in cloud mode and adding a collection. To get started, simply do:

> bin/solr -e cloud -force

This starts an interactive session to walk you through the steps of setting up a simple SolrCloud cluster with embedded ZooKeeper.

The script starts by asking you how many Solr nodes you want to run in your local cluster, with the default being 2.

Welcome to the SolrCloud example!

This interactive session will help you launch a SolrCloud cluster on your local workstation.
To begin, how many Solr nodes would you like to run in your local cluster? (specify 1-4 nodes) [2]
The script supports starting up to 4 nodes, but we recommend using the default of 2 when starting out. These nodes will each exist on a single machine, but will use different ports to mimic operation on different servers.

Next, the script will prompt you for the port to bind each of the Solr nodes to, such as:

> Please enter the port for node1 [8983]

Choose any available port for each node; the default for the first node is 8983 and 7574 for the second node. The script will start each node in order and show you the command it uses to start the server, such as:

> solr start -cloud -s example/cloud/node1/solr -p 8983

The first node will also start an embedded ZooKeeper server bound to port 9983. The Solr home for the first node is in example/cloud/node1/solr as indicated by the -s option.

After starting up all nodes in the cluster, the script prompts you for the name of the collection to create:

> Please provide a name for your new collection: [gettingstarted]

The suggested default is "gettingstarted" but you might want to choose a name more appropriate for your specific search application.

Next, the script prompts you for the number of shards to distribute the collection across. Sharding is covered in more detail later on, so if you’re unsure, we suggest using the default of 2 so that you can see how a collection is distributed across multiple nodes in a SolrCloud cluster.

Next, the script will prompt you for the number of replicas to create for each shard. Replication is covered in more detail later in the guide, so if you’re unsure, then use the default of 2 so that you can see how replication is handled in SolrCloud.

Lastly, the script will prompt you for the name of a configuration directory for your collection. You can choose basic_configs, data_driven_schema_configs, or sample_techproducts_configs. The configuration directories are pulled from server/solr/configsets/ so you can review them beforehand if you wish. The data_driven_schema_configs configuration (the default) is useful when you’re still designing a schema for your documents and need some flexiblity as you experiment with Solr.

At this point, you should have a new collection created in your local SolrCloud cluster. To verify this, you can run the status command:

> bin/solr status

If you encounter any errors during this process, check the Solr log files in example/cloud/node1/logs and example/cloud/node2/logs.

You can see how your collection is deployed across the cluster by visiting the cloud panel in the Solr Admin UI: http://localhost:8983/solr/>/~cloud. Solr also provides a way to perform basic diagnostics for a collection using the healthcheck command:

bin/solr healthcheck -c gettingstarted
The healthcheck command gathers basic information about each replica in a collection, such as number of docs, current status (active, down, etc), and address (where the replica lives in the cluster).

Documents can now be added to SolrCloud using the Post Tool.

To stop Solr in SolrCloud mode, you would use the bin/solr script and issue the stop command, as in:

> bin/solr stop -all

Restarting Nodes

You can restart your SolrCloud nodes using the bin/solr script. For instance, to restart node1 running on port 8983 (with an embedded ZooKeeper server), you would do:

> bin/solr restart -c -p 8983 -s example/cloud/node1/solr

To restart node2 running on port 7574, you can do:

> bin/solr restart -c -p 7574 -z localhost:9983 -s example/cloud/node2/solr

Notice that you need to specify the ZooKeeper address (-z localhost:9983) when starting node2 so that it can join the cluster with node1.

Adding a node to a cluster
Adding a node to an existing cluster is a bit advanced and involves a little more understanding of Solr. Once you startup a SolrCloud cluster using the startup scripts, you can add a new node to it by:

> mkdir <solr.home for new solr node>
> cp <existing solr.xml path> <new solr.home>
> bin/solr start -cloud -s solr.home/solr -p <port num> -z <zk hosts string>

Notice that the above requires you to create a Solr home directory. You either need to copy solr.xml to the solr_home directory, or keep in centrally in ZooKeeper /solr.xml.

Example (with directory structure) that adds a node to an example started with "bin/solr -e cloud":

> mkdir -p example/cloud/node3/solr
> cp server/solr/solr.xml example/cloud/node3/solr
> bin/solr start -cloud -s example/cloud/node3/solr -p 8987 -z localhost:9983

The previous command will start another Solr node on port 8987 with Solr home set to example/cloud/node3/solr. The new node will write its log files to example/cloud/node3/logs.

Adding Documents Using XML

To add the above data into Solr index, we need to prepare an XML document, as shown below. Save this document in a file with the name sample.xml.

```xmls
<add> 
   <doc> 
      <field name = "id">001</field> 
      <field name = "first name">Rajiv</field> 
      <field name = "last name">Reddy</field> 
      <field name = "phone">9848022337</field> 
      <field name = "city">Hyderabad</field> 
   </doc>  
   <doc> 
      <field name = "id">002</field> 
      <field name = "first name">Siddarth</field> 
      <field name = "last name">Battacharya</field> 
      <field name = "phone">9848022338</field> 
      <field name = "city">Kolkata</field> 
   </doc>  
   <doc> 
      <field name = "id">003</field> 
      <field name = "first name">Rajesh</field> 
      <field name = "last name">Khanna</field> 
      <field name = "phone">9848022339</field> 
      <field name = "city">Delhi</field> 
   </doc>  
   <doc> 
      <field name = "id">004</field> 
      <field name = "first name">Preethi</field> 
      <field name = "last name">Agarwal</field> 
      <field name = "phone">9848022330</field> 
      <field name = "city">Pune</field> 
   </doc>  
   <doc> 
      <field name = "id">005</field> 
      <field name = "first name">Trupthi</field> 
      <field name = "last name">Mohanthy</field> 
      <field name = "phone">9848022336</field> 
      <field name = "city">Bhuwaeshwar</field> 
   </doc> 
   <doc> 
      <field name = "id">006</field> 
      <field name = "first name">Archana</field> 
      <field name = "last name">Mishra</field> 
      <field name = "phone">9848022335</field> 
      <field name = "city">Chennai</field> 
   </doc> 
</add>
```

As you can observe, the XML file written to add data to index contains three important tags namely, <add> </add>, <doc></doc>, and < field >< /field >.

add − This is the root tag for adding documents to the index. It contains one or more documents that are to be added.

doc − The documents we add should be wrapped within the <doc></doc> tags. This document contains the data in the form of fields.

field − The field tag holds the name and value of the fields of the document.

After preparing the document, you can add this document to the index using any of the means discussed in the previous chapter.

Suppose the XML file exists in the bin directory of Solr and it is to be indexed in the core named my_core, then you can add it to Solr index using the post tool as follows −

> [bits@localhost bin]$ ./post -c my_core sample.xml
