---
name: maven-project
description: Use for ANY Java project using Maven (pom.xml, mvn, mvnw) — builds, tests, troubleshooting. Not for Gradle or plain-Java projects.
disable-model-invocation: true
user-invocable: true
---

# Maven Project

- Shell: Bash. Never PowerShell/CMD.
- Build tool: global `mvn`, never `./mvnw`.
- Tests: run only the affected class(es), not the full suite.
  `mvn test -Dtest=ClassA,ClassB` / `-Dtest=ClassA#method`
- Parse result from: `Tests run:|BUILD SUCCESS|BUILD FAILURE|ERROR`
- On green: stop. On red: read the failure, fix, re-run only that test — don't re-run the whole suite.
