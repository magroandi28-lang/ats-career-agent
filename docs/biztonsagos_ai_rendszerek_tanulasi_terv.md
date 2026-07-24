# Biztonságos vállalati AI-rendszerek – tanulási terv és portfólió projekt

**Készült:** 2026. július 23.
**Tempó:** villámgyors, pár nap, teljes idős ráfordítással — minden lépés gyakorlatban, elmélet csak annyi, hogy értsd mit miért csinálsz
**Cél:** megérteni és gyakorlatban felépíteni, hogyan használhat egy cég AI-t úgy, hogy a saját fejlesztései és adatai ne kerüljenek ki — majd ebből egy bemutatható portfólió-darabot készíteni.

---

## Miért ezt az utat választjuk

Két nagy irány van a "privát AI" kiépítésére: **felhős dedikált instance** (Azure OpenAI, AWS Bedrock) és **self-hosted nyílt modell** (Llama, Mistral saját szerveren). A tervben mindkettőt megtanulod, de a felhős résznél **Azure OpenAI Service**-re fókuszálunk elsőként, mert:

- EU-s adatközpontok vannak rá, ami GDPR szempontból egyszerűbbé teszi a megfeleltetést egy magyar/EU-s cégnél.
- A magyar és EU-s vállalati piacon (bankok, biztosítók, gyártó cégek) messze ez a leggyakrabban kért készség AI-integrációs pozíciókban, mert ezek a cégek jellemzően már Microsoft-ökoszisztémában vannak (Azure AD, Microsoft 365).
- A hálózati izolációs koncepció (VNet, private endpoint) 1:1 átvihető AWS Bedrockra is, ha később arra lesz szükséged — a mögöttes gondolkodás ugyanaz.

A self-hosted résznél **Ollama-val kezdünk** (gyors, egyszerű, jó a tanuláshoz), majd **vLLM-re** lépünk (ez a valódi éles, több felhasználós szerverelés eszköze).

> **Frissítés (2026.07.23):** az Azure próbaidőszak lejárt, a fiók 2 nap múlva törlődik, ha nem történik előfizetés-frissítés. Emiatt a sorrendet megcseréltük: **előbb a self-hosted rész (ingyenes, azonnal indítható), utána az Azure**, amint rendeződik az előfizetés (fizetős + költségkorlát, vagy Azure for Students, ha jogosult rá).

---

## Nap 1 — Azure OpenAI privát kiépítés (gyakorlatban)

**Cél a nap végére:** saját Azure OpenAI instance, ami kizárólag a saját virtuális hálózatodon (VNet) belülről érhető el, kívülről nem.

**Amit érteni kell hozzá (5 perc, nem több):** a VNet egy elszigetelt hálózati doboz a felhőben; a private endpoint ennek a doboznak ad egy privát IP-t az Azure OpenAI-hoz, így a forgalom sosem megy ki a publikus internetre; a privát DNS zóna kell ahhoz, hogy a szolgáltatás neve erre a privát IP-re oldódjon fel, ne a publikusra.

**Gyakorlat — lépésről lépésre (ingyenes Azure próba-előfizetéssel megy):**
1. Erőforráscsoport létrehozása, majd egy VNet két subnettel (egy az "alkalmazásnak", egy a "private endpointnak")
2. Azure OpenAI Service erőforrás létrehozása
3. Private endpoint létrehozása és hozzákapcsolása az Azure OpenAI erőforráshoz
4. Privát DNS zóna beállítása
5. Teszt: egy VNeten belüli virtuális gépről érd el az API-t, majd bizonyítsd be, hogy kívülről NEM érhető el

**Kész, ha:** működik a privát instance, és kívülről tényleg 403/timeout-ot kapsz.

**Forrás:**
- [Securing Azure OpenAI inside a virtual network with private endpoints – Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/network?view=foundry-classic)
- [Azure OpenAI Private Endpoints: Connecting Across VNet's – Microsoft Community Hub](https://techcommunity.microsoft.com/blog/azurearchitectureblog/azure-openai-private-endpoints-connecting-across-vnet%E2%80%99s/3913325)
- [How to Set Up Azure OpenAI Service with Private Endpoints for Network Isolation](https://oneuptime.com/blog/post/2026-02-16-how-to-set-up-azure-openai-service-with-private-endpoints-for-network-isolation/view)

---

## Nap 2 — Self-hosted nyílt modellek: Ollama, majd vLLM (gyakorlatban)

**Cél a nap végére:** saját szerveren (otthoni gép vagy olcsó felhős VM) futó, hitelesítéssel védett LLM endpoint, mindkét eszközzel kipróbálva.

**Amit érteni kell (5 perc):** Ollama = egyszerű, egyfelhasználós, gyorsan futtatható; vLLM = production-grade, sok egyidejű felhasználót tud kiszolgálni sokkal nagyobb átbocsátással (kb. 2-9x), de nehezebb beüzemelni.

**Gyakorlat:**
1. Telepítsd az Ollamát, futtass rajta egy Llama vagy Mistral modellt lokálisan
2. Nézd meg a kvantálási beállítást (pl. Q4_K_M) — ez szabja meg, mennyi memória kell
3. Telepítsd a vLLM-et, indíts el vele ugyanazt a modellt, küldj rá párhuzamos kéréseket, hasonlítsd össze a sebességet Ollamaval
4. Tedd hitelesítés (API kulcs) és reverse proxy (pl. Nginx) mögé az endpointot — enélkül bárki eléri, aki rálát a gépre

**Kész, ha:** van egy saját, jelszóval/API-kulccsal védett endpointod, és tudod mondani egy mondatban, mikor válasszuk Ollamát és mikor vLLM-et.

**Forrás:**
- [vLLM vs Ollama vs LM Studio: The 2026 Production Self-Host Benchmark](https://codersera.com/blog/vllm-vs-ollama-vs-lm-studio-production-2026/)
- [Ollama vs vLLM 2026: throughput összehasonlítás](https://tech-insider.org/vllm-vs-ollama-2026/)
- [LLM Hosting in 2026: Local, Self-Hosted and Cloud Infrastructure Compared](https://www.glukhov.org/llm-hosting/)

---

## Nap 3 — Jogosultság-alapú RAG architektúra megépítése (gyakorlatban)

**Cél a nap végére:** működő mini-rendszer, ahol a felhasználó csak azt kapja vissza válaszban, amihez ténylegesen jogosult.

**Amit érteni kell (5 perc):** RBAC = jogosultság a szerepkörhöz kötve (ezt fogjuk használni, ez a legegyszerűbb és a leggyakoribb vállalati megoldás); post-retrieval filtering = előbb lekéri a rendszer a releváns dokumentumokat, utána egy külön ellenőrzés kiszűri, amihez a user nem jogosult, mielőtt a modell látná — ez a skálázhatóbb megoldás, mint előre szűrni.

**Gyakorlat:**
1. Állíts be egy egyszerű vektor adatbázist (Chroma vagy FAISS) pár teszt-dokumentummal, amikhez különböző szerepköröket rendelsz (pl. "junior", "vezető")
2. Építs egy szűrő réteget, ami a keresési találatokból kidobja azt, amihez az adott szerepkörnek nincs joga — mielőtt a modell kontextusába kerülne
3. Kösd össze a Nap 1-2-ben elkészült modell-endpointtal (akár az Ollama, akár az Azure OpenAI instance)
4. Rakj rá naplózást: ki, mikor, mit kérdezett, mihez fért hozzá

**Kész, ha:** két különböző szerepkörrel lefuttatva ugyanazt a kérdést, ténylegesen más választ kapsz — mert más dokumentumokhoz fér hozzá mindkettő.

**Forrás:**
- [RAG with Access Control – Pinecone](https://www.pinecone.io/learn/rag-access-control/)
- [Document-Level RBAC for RAG Pipelines: The 2026 Enterprise Architecture Guide](https://truto.one/blog/how-to-maintain-document-level-rbac-in-enterprise-rag-pipelines/)
- [RAG & RBAC integration – Elastic](https://www.elastic.co/search-labs/blog/rag-and-rbac-integration)

---

## Nap 4 — Portfólió projekt: csomagolás, dokumentálás

A Nap 3-ban már működik a technikai mag. Ma ezt csomagolod be bemutatható portfólió-darabbá.

### Amit el kell készítened
1. **Architektúra dokumentum** (a Nap 3 logikáját írd le) — ábrával, indoklással
2. **README**, ami elmagyarázza, milyen üzleti problémára válasz ez (adatszivárgás megelőzése AI-használat mellett)
3. **Rövid demo forgatókönyv** — 3-4 perces bemutatás arra az esetre, ha interjún meg kell mutatnod

### Hogyan mutasd be interjún
Ez nem egy "megcsináltam egy chatbotot" projekt, hanem egy "megértettem, hogyan gondolkodik egy cég a kockázatról" projekt. Az interjún érdemes elmondani:
- Milyen üzleti kockázatot old meg (adatszivárgás, jogosulatlan hozzáférés)
- Milyen alternatívákat mérlegeltél (felhős privát instance vs. self-hosted) és miért az adott megoldást választottad egy konkrét helyzetben
- Mit tanultál a pre-filtering vs. post-filtering döntésről

---

## Gyors áttekintő táblázat a döntéshez (mikor melyik megoldás)

| Helyzet | Ajánlott megoldás |
|---|---|
| Nagy cég, EU-s adatvédelmi megfelelés, van Microsoft-infrastruktúra | Azure OpenAI + Private Endpoint |
| Nagyon szigorú, légrésű (air-gapped) környezet, semmi nem mehet ki | Self-hosted (Ollama/vLLM) saját szerveren |
| Sok egyidejű felhasználó, teljesítmény-kritikus | Self-hosted vLLM dedikált GPU-n |
| Gyors prototípus, kevés felhasználó, korlátozott IT-erőforrás | Self-hosted Ollama vagy felhős API zero-retention szerződéssel |

---

## Összegzés — a 4. nap végén ezekkel kell rendelkezned

1. Működő, hálózatilag izolált Azure OpenAI instance (vagy legalább a lépések dokumentált ismerete, ha az ingyenes előfizetés elfogy)
2. Saját szerveren futó, hitelesítéssel védett self-hosted LLM (Ollama + vLLM tapasztalat)
3. Saját kezűleg felépített, működő jogosultság-alapú RAG mini-rendszer
4. Írásos architektúra-dokumentum + README + demo forgatókönyv a portfóliódban

Ez a négy pont együtt pontosan azt bizonyítja egy leendő munkáltatónak, amit a legelején fontosnak mondtál: hogy a biztonság és a felelősségteljes AI-használat nem utólagos gondolat nálad, hanem a tervezés része.
