@echo off
set JAVA_HOME=C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot
set PATH=%JAVA_HOME%\bin;D:\develop\tools\apache-maven-3.9.9\bin;%PATH%
cd /d %~dp0ruoyi-cs
mvn -s settings.xml spring-boot:run
