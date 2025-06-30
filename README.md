# Filarkiv Cleanup Robot – Procesbeskrivelse

Denne robot er designet til at rydde op i sager og tilknyttede filer i Filarkiv ved brug af OpenOrchestrator-frameworket. Den anvender kø-baseret afvikling og håndterer både autentificering, datasletning og opfølgende API-kald.

---

## Formål

Robotten modtager en sag (CaseID) via køen og udfører følgende:
- Henter en gyldig adgangstoken til Filarkiv
- Finder alle fil-ID'er relateret til sagen
- Sletter sagen fra Filarkiv via API
- Poster liste over slettede fil-ID’er til et eksternt endpoint for videre oprydning

---

## Procesoversigt

### 1. Token-håndtering

Funktionen `GetFilarkivToken`:
- Validerer tidsstempel for eksisterende token (fra OpenOrchestrator konstant)
- Hvis token er ældre end 30 minutter, hentes et nyt
- Token og nyt tidsstempel gemmes i Orchestrator

### 2. Data fra køelement

Køelementet forventes at indeholde:
```json
{
  "FilArkivCaseId": "<UUID>"
}
