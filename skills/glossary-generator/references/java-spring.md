# Java / Spring Boot Scanning Profile

Load when `pom.xml` / `build.gradle*` is present.

## 1. Entities
`grep -rl "@Entity" --include="*.java" .`
Per match: class name → `term` (PascalCase → spaced words). `@Table(name=...)` → table name in `code_refs`. Each business-relevant `@Column` → own row (skip audit fields per the base skill's boilerplate rule). Javadoc above class/field → grounding source.

## 2. DTOs / request-response
`grep -rl "class.*\(Request\|Response\|Dto\|DTO\)" --include="*.java" .` — also check Lombok `@Data`/`@Value` classes outside `dto`/`request`/`response`/`payload`/`api` paths. High priority — what other teams/ops actually see.
- `@JsonProperty("...")` → capture as alias (often the exact field ops sees in raw API responses/logs).
- `@Schema(description="...")` → strong grounding source.

## 3. Enums
`grep -rl "public enum" --include="*.java" .`
Each business-visible constant (`PENDING`, `FAILED`, etc.) → own row; skip purely internal states. Javadoc on the constant → grounding source.

## 4. DB tables/columns
Prefer migrations over annotations (actual deployed schema): `find . -path "*/db/migration/*" -name "*.sql"` and Liquibase changelogs. Parse `CREATE TABLE`/`ALTER TABLE ADD COLUMN` + inline `-- comments` (strong grounding).

## 5. Public API fields
`find . -name "openapi*.y*ml" -o -name "swagger*.json"` — if present, highest-priority source for this category; `description` fields = direct grounding. No spec file → fall back to `@RestController` signatures / DTO types (category 2).

## jOOQ-generated code: schema truth, not a definition source
Check for jOOQ (`jooq-codegen` plugin, or a generated package like `**/jooq/tables/**`).
- **Use** as the most current, authoritative table/column source for category 4 — generated from the live/migrated schema. Cross-reference against the migration scan; jOOQ has something migrations don't → trust jOOQ, add it.
- **Don't use** as a `definition_en` grounding source — no author-written meaning, just derived names. jOOQ-only match = `confidence=name-only`.
- **Don't** pull business terms from jOOQ DSL *usage* in app code (e.g. `.select(...).from(SETTLEMENT_BATCH)`) — that's code using the schema, not a new meaning source.

## Skip
`@Configuration`/`@Component`/`@Service`/`@Repository` with no `@Entity`/DTO shape (wiring, not domain). Generated MapStruct/Lombok code. Test classes, `target/`/`build/`. Audit-only fields (`id` unless business-meaningful, `createdAt`, `updatedAt`, `version`).
