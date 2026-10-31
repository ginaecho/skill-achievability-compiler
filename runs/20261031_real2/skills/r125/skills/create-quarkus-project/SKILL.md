---
name: create-quarkus-project
description: 'Create a new Quarkus project (Maven or Gradle) with the Quarkus CLI, [host-1] API or Maven plugin, choose extensions, and run it in dev mode. Use when asked to scaffold, bootstrap or start a Quarkus application or REST API.'
---

# Create a Quarkus Project

## 1. Detect the environment

```bash
java -version          # Java 17, 21 or 25 (Quarkus 3.40 recommends 25, 3.27 recommends 21)
quarkus --version      # optional Quarkus CLI
./mvnw -v || mvn -v    # or ./gradlew -v
```

If the folder already contains a Quarkus project (`io.quarkus.platform` BOM, `quarkus-maven-plugin`, or `io.quarkus` Gradle plugin), do NOT scaffold: read its Quarkus version and keep it. For a new project, use the stream marked recommended on [url-1] (an LTS stream; see also [url-2]), and do not invent a patch version: let the tool pick it. Quarkus 4.0 is still a beta, so do not use it unless asked. If an extension is missing from the recommended stream, the CLI silently picks an older stream; check `quarkus.platform.version` in the generated build file.

## 2. Scaffold (pick one)

Quarkus CLI (install via [url-3] , e.g. SDKMAN `sdk install quarkus`):

```bash
quarkus create app com.example:demo \
  --extension='rest-jackson,hibernate-orm-panache,jdbc-postgresql,hibernate-validator,smallrye-health' \
  --java=21 --maven        # or --gradle
```

No CLI: Maven plugin (pin the version to the current release from [url-4], replace `QUARKUS_VERSION` below with it):

```bash
mvn io.quarkus.platform:quarkus-maven-plugin:QUARKUS_VERSION:create \
  -DprojectGroupId=com.example -DprojectArtifactId=demo \
  -Dextensions='rest-jackson,hibernate-orm-panache,jdbc-postgresql' \
  -DbuildTool=maven        # or gradle
```

Or generate from the [url-5] web UI / REST API (`[url-6]`) and unzip.

## 3. Choose extensions

| Need | Extension |
|---|---|
| REST + JSON | `rest-jackson` (Quarkus REST; not legacy `resteasy`) |
| Database ORM | `hibernate-orm-panache`, `jdbc-postgresql` |
| Validation | `hibernate-validator` |
| Health / metrics | `smallrye-health`, `micrometer-registry-prometheus` |
| Auth | `oidc` or `smallrye-jwt` |
| OpenAPI | `smallrye-openapi` |
| REST client | `rest-client-jackson` |
| Container | `container-image-jib` (or `container-image-docker`) |

Add later with `quarkus extension add <name>` or `./mvnw quarkus:add-extension -Dextensions=<name>`; `quarkus extension list --installable` lists options.

## 4. Layout and run

```
src/main/java/...          # resources, services, entities
src/main/resources/application.properties
src/main/docker/           # Dockerfile.jvm, Dockerfile.native, ...
src/test/java/...          # @QuarkusTest / @QuarkusIntegrationTest
```

```bash
./mvnw quarkus:dev         # or: quarkus dev / ./gradlew quarkusDev
```

Generated tests include a `*IT` class that Maven skips by default (`<skipITs>true</skipITs>` in the template); run it with `./mvnw verify -DskipITs=false` or `-Dnative`. Dev mode gives live reload, Dev UI at [url-7], Dev Services (auto containers), and continuous testing (press `r`). Package: `./mvnw package` (runnable `target/quarkus-app/quarkus-run.jar`).

## References

- [Configuration](references/configuration.md)
- [Database (Dev Services, Hibernate, Flyway/Liquibase)](references/database.md)
- [Security basics](references/security.md)
- [Container images](references/container-image.md)
- [Local runtime insights (BootUI)](references/local-runtime-insights.md)

Verified (scaffold, `./mvnw verify`, `./gradlew build`, dev mode, Dev Services PostgreSQL, JDK 26 with Java 25 release) on Quarkus 3.40.1 (current recommended LTS stream) and `./mvnw verify` on 3.27.6 (older LTS).

Related skills: `quarkus-dev-services-and-testing`, `quarkus-native-and-container`.

## Upstream sources (read before upgrading)

Fetch the page for the target version; prefer it over this skill when they conflict.

- `quarkus update` (automated upgrade, uses OpenRewrite): <[url-8]>
- Migration guides, one wiki page per minor: <[url-9]> (change the version)
- Release announcements: <[url-10]>
- LTS policy and current LTS: <[url-11]>
