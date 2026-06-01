# Contribuir a Open Data Jalisco

¡Gracias por considerar contribuir! Este documento describe el flujo formal para reportar issues, enviar pull requests y firmar tus contribuciones bajo los términos de la AGPLv3.

Antes de leer esta guía técnica, es importante que conozcas el espíritu del proyecto: <https://odj.n0kemm.dev/> y el [manifiesto](docs/MANIFEST.md). Las contribuciones técnicas deben ser coherentes con la neutralidad política, la trazabilidad documental y la protección de datos personales que el manifiesto exige.

---

## 1. Licencia de las contribuciones

Todo el código del repositorio se publica bajo **GNU Affero General Public License v3.0 o posterior (AGPL-3.0-or-later)**, ver [`LICENSE`](LICENSE).

Al enviar un pull request aceptas que tu contribución se distribuya bajo esos mismos términos.

## 2. Developer Certificate of Origin (DCO)

Open Data Jalisco usa el [Developer Certificate of Origin v1.1](https://developercertificate.org/) en lugar de un CLA. Es un texto corto que firmas con cada commit y certifica que tienes derecho a contribuir el código:

> By making a contribution to this project, I certify that:
>
> (a) The contribution was created in whole or in part by me and I have the right to submit it under the open source license indicated in the file; or
> (b) The contribution is based upon previous work that, to the best of my knowledge, is covered under an appropriate open source license and I have the right under that license to submit that work with modifications [...]; or
> (c) The contribution was provided directly to me by some other person who certified (a), (b) or (c) and I have not modified it.
>
> (d) I understand and agree that this project and the contribution are public and that a record of the contribution (including all personal information I submit with it [...]) is maintained indefinitely and may be redistributed [...]

### Firmar tus commits

Cada commit en tu PR debe llevar la línea `Signed-off-by`. Para que git la agregue automáticamente:

```bash
git commit -s -m "feat(scrapers): soportar paginación SAPUMU"
```

El flag `-s` produce un trailer así:

```
Signed-off-by: Tu Nombre <tu@email.com>
```

Configura tu identidad git una sola vez:

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu@email.com"
```

Si olvidaste firmar un commit:

```bash
git commit --amend --signoff
# o, para varios commits:
git rebase --signoff HEAD~N
```

PRs sin sign-off no serán mergeados.

## 3. Antes de abrir un PR

1. **Abre un issue primero** si el cambio es no-trivial (nuevo scraper, nuevo extractor, cambio en el modelo de dominio, cambio en API pública). Para typos, docs o bugs pequeños puedes ir directo al PR.
2. **Confirma scope** con los mantenedores. El manifiesto §10 lista qué tipo de contribuciones son aceptables y cuáles no (no se aceptan inferencias políticas como metadata, alteración de hashes históricos, etc.).
3. **Fork + branch**. Trabaja en una rama descriptiva: `feat/scraper-zapopan`, `fix/pdf-extractor-empty-pages`, `docs/contributing`.

## 4. Estilo de código

El proyecto usa `ruff` para lint/format y `mypy` en modo estricto.

```bash
uv run ruff format .
uv run ruff check . --fix
uv run mypy src
```

Convenciones específicas:

- **Arquitectura hexagonal**. No mezcles capas: el `domain/` no importa de `adapters/`, los `adapters/` implementan `ports/`.
- **Nuevos scrapers** van en `src/open_data_jalisco/adapters/scrapers/` e implementan el puerto `Scraper`.
- **Nuevos extractores** van en `src/open_data_jalisco/adapters/extraction/` e implementan el puerto `TextExtractor`, registrados en `extraction/registry.py`.
- **Nuevas fuentes municipales** se agregan como YAML en `datasets/sources/`, no como código.
- **Sin docstrings de varios párrafos.** Una línea por función pública si la firma no es autoexplicativa.
- **Sin comentarios `# TODO` en main**. Si algo queda pendiente, abre un issue.

Todo archivo `.py` nuevo debe llevar el header SPDX:

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors
```

## 5. Tests

- Los tests unitarios viven en `tests/unit/` — no pueden tocar red, disco no temporal, ni base de datos.
- Los tests de integración viven en `tests/integration/` y pueden requerir Postgres arriba.

```bash
make test-unit          # rápido, lo que CI exige siempre
make test               # suite completa, requiere docker compose up -d postgres
```

Toda funcionalidad nueva debe llegar con tests. Los tests también son contribuciones de primera clase: si encuentras un caso sin cubrir, manda un PR solo con el test (failing) y lo discutimos.

## 6. Formato de commits

Estilo [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>(<scope opcional>): <resumen en imperativo, <72 chars>

<cuerpo opcional explicando el "por qué", no el "qué">

Signed-off-by: Tu Nombre <tu@email.com>
```

Tipos comunes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`.

Ejemplo:

```
feat(scrapers): agregar scraper para portal de Zapopan

El portal SAPUMU de Zapopan publica documentos bajo /transparencia/articulo_8
con paginación distinta a Tala. Este scraper reusa _sapumu_parser y agrega
un descubrimiento incremental por rango de IDs.

Signed-off-by: Tu Nombre <tu@email.com>
```

## 7. Pull requests

Antes de abrir un PR:

- [ ] Commits firmados (`-s`).
- [ ] `ruff format`, `ruff check`, `mypy` pasan sin warnings.
- [ ] `make test-unit` pasa local.
- [ ] Para cambios en API pública o nuevos endpoints: actualizado `docs/FRONTEND_GUIDE.md` y el README si corresponde.
- [ ] Para nuevos scrapers/extractores: hay al menos un test con fixture realista.
- [ ] El PR se enfoca en un solo cambio. Refactors no relacionados van en PRs separados.

En el cuerpo del PR responde tres preguntas:

1. **¿Qué cambió?** Resumen técnico.
2. **¿Por qué?** Motivación, link al issue.
3. **¿Cómo lo probaste?** Pasos de verificación manual + tests automatizados.

## 8. Revisión

- Los mantenedores intentarán revisar dentro de una semana. Si pasaron 10 días sin actividad, escribe un comentario para reactivar.
- Los cambios solicitados son normales. No los tomes personal — vienen del manifiesto, no de juicio sobre el contribuidor.
- Se mergea con `Squash and merge` por defecto. Asegúrate de que el mensaje final de squash mantenga al menos un `Signed-off-by` (los DCO bots de GitHub verifican esto).

## 9. Datos sensibles y de personas

**Nunca incluyas** en un PR:

- documentos públicos reales con datos personales sin tachar (RFC, CURP, domicilios particulares, teléfonos personales);
- credenciales, tokens, cookies de sesión, API keys;
- URLs internas de portales no públicos;
- snapshots de la base de datos de producción.

Las fixtures de prueba deben usar documentos sintéticos o documentos públicos sin datos personales identificables.

## 10. Reportar vulnerabilidades de seguridad

**No abras un issue público** para vulnerabilidades. Reporta de forma privada:

- GitHub Security Advisory en <https://github.com/Chaetard/open-data-jalisco/security/advisories/new>, o
- correo al mantenedor: ver perfil GitHub.

Incluye pasos de reproducción y, si aplica, una prueba de concepto. Reconocemos el reporte en menos de 72 hr.

## 11. Código de conducta

Se espera trato respetuoso en issues, PRs y discusiones. El proyecto es apartidista: no se aceptan comentarios que conviertan inconsistencias documentales en acusaciones políticas. La discusión técnica se mantiene técnica.

---

¿Dudas sobre este documento? Abre un issue con la etiqueta `meta` o `contributing`.
