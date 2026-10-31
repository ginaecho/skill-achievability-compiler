# Upstream sources (java-upgrade)

Fetch the page for the **target** version before editing; prefer it over this skill when they conflict. Replace `N` with the target JDK (17, 21, 25).

## JDK

- OpenJDK release page (JEP list per release): <[url-1]> (e.g. <[url-2]>, <[url-3]>)
- JEP index: <[url-4]>
- Oracle JDK release notes (incompatible changes, removals): <[url-5]> (change `21` to the target)
- Oracle JDK migration guide: <[url-6]> and <[url-7]>
- Find removed or deprecated API usage: `jdeprscan` <[url-8]>, `jdeps` <[url-9]>
- Adoptium support and release schedule: <[url-10]>

## Build tools and agents

- Gradle / JDK compatibility matrix: <[url-11]>
- Maven Compiler Plugin (`release`, `--enable-preview`): <[url-12]>
- Lombok changelog: <[url-13]>
- Byte Buddy (used by Mockito/Hibernate; check the supported class file version): <[url-14]>
- JaCoCo changes (JDK support per release): <[url-15]>
- Mockito: <[url-16]>

## Automation (OpenRewrite)

- `org.openrewrite.java.migrate.UpgradeToJava17`: <[url-17]>
- `org.openrewrite.java.migrate.UpgradeToJava21`: <[url-18]>
- `org.openrewrite.java.migrate.UpgradeToJava25`: <[url-19]>

## Related tooling

- The external Microsoft plugin `modernize-java` (<[url-20]>, listed in this repository's `plugins/external.json`) is the more powerful option for automated, large or multi-step upgrades (upgrade plan, build-fix loops, CVE validation). This skill works without it; see "Need a more powerful, automated upgrade?" in `SKILL.md`.
