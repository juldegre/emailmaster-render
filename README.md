# EmailMaster Render Pack

## Déploiement sur Render

1. Mets ces fichiers sur un repo GitHub
2. Connecte-le à Render
3. Configure les variables d'environnement :
   - CREDENTIALS_JSON
   - TOKEN_JSON
   - LAURE_EMAILS
   - SEND_SUMMARY_TO
   - TARGET_LABEL
   - CHECK_INTERVAL_MINUTES (optionnel)
4. Lance le service et teste `/health` puis `/cron`.
