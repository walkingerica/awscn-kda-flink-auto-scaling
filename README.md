# awscn-kda-flink-auto-scaling
## Requirements

目前Kinesis Data Analytics(以下称KDA) 有自带的自动扩展功能，遵守以下的原则：
•	当您的 CPU 使用率保持在 75% 或以上 15 分钟时，您的应用程序可以扩展（增加并行度）。
•	当 CPU 使用率在六个小时内保持在 10％ 以下时，应用程序将缩小（减少并行度）。
但是很多用户的场景是希望结合自己的应用情况通过自定义的方式进行自动拓展，例如通过检测KDA的cpuUtilization进行扩展，本文示例通过此进行。

## Architecture 

该架构使用到的服务和作用：
•	Cloudwatch: 观测 KDA的指标，这里观测的是cpuUtilization
•	Application Auto Scaling：用于弹性伸缩可扩展的资源
•	API Gateway：通过AGW终端节点到自定义资源
•	Lambda: KDA并行度的扩展代码运行在Lambda中
•	Parameter Store: 存储Desired 并行度值
•	Kinesis Data Analytics: 用户需要扩展并行度的KDA服务
•	Kinesis Data Stream: 测试使用，将数据输入到KDA中进行分析，从而提升CPU 使用率。

自动扩展架构如下图：
![Image text](https://github.com/walkingerica/awscn-kda-flink-auto-scaling/blob/main/arch1.png)


 

测试架构如下图：
![Image text](https://github.com/walkingerica/awscn-kda-flink-auto-scaling/blob/main/arch2.png)


 

## Steps
1.	首先准备Kinesis Data Streams，Kinesis Analytics和生成数据的Python 代码, 请参考这个链接，可以建立起测试环境。
2.	通过Github 上的CloudFormation 模版，创建自动扩展架构。CloudFormation 模版已经根据AWS中国区环境和客户的需求进行了修改，直接使用即可。
3.	在测试好上面的环境后，可以使用用户的Autoscaling配置和Lambda代码替换。


## Know Issues and solutions
1.	CloudFormation 模版创建失败， 提示502错误。解决办法，1）在创建CloudFormation Stack的时候选择” Preserve successfully provisioned resources”  2）API Gateway和Lambda已经部署，通过API Gateway的Test Invoke功能向Lambda请求  3）查看Lambda的Log
2.	CloudFormation 模版创建失败 提示“Error reading entity from input stream”。KDA创建添加Running Application后解决。

## Reference

[kda-flink-app-autoscaling](<https://github.com/aws-samples/kda-flink-app-autoscaling/>)

