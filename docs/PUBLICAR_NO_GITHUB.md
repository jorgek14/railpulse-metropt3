# Como publicar o RailPulse no GitHub, com histórico legítimo

1. Crie uma conta no https://github.com, se ainda não tiver.
2. Crie um repositório **vazio** chamado `railpulse-metropt3`. Não peça README adicional na criação: este pacote já traz um.
3. Descompacte o ZIP do projeto em seu computador, abra **Git Bash** ou terminal na pasta extraída.
4. Confirme que o CSV bruto **não está lá**: `git status` após inicializar / `.gitignore` o ignora.
5. Execute:

```bash
git init
git add .
git commit -m "Organiza reprodução MetroPT-3 e protótipo RailPulse"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/railpulse-metropt3.git
git push -u origin main
```

O GitHub pode solicitar autenticação pelo navegador ou método configurado. Não cole tokens em arquivos nem no chat. Se preferir sem terminal, use GitHub Desktop e faça publish do repositório local.

6. Abra o GitHub; revise README, `notebooks/`, `analises/`, `iot_monitor/` e `dados_demo/`.
7. Em https://colab.research.google.com/, abra **GitHub**, procure seu usuário e repo, escolha notebook 01. Na primeira célula preencha `git_repo` com o URL acima (caso o código ainda não esteja no ambiente), ou envie o ZIP do repositório solicitado.
8. Refaça os exercícios, produza commits com alterações de verdade e registre o que você executou e compreendeu. Os commits mostram histórico de organização e revisão, **não comprovam autoria exclusiva ou origem do código**.

**CSV integral:** GitHub web só aceita até 25 MiB por arquivo e o Git normal até 100 MiB; o CSV original tem ~209 MB, por isso mantemos apenas demonstrações pequenas e um caminho para o UCI.
