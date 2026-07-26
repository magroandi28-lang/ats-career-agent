import Link from "next/link";

export const metadata = {
  title: "Adatkezelési tájékoztató — Karrier-Ügynökség",
};

const VERZIO = "2026-07-26";

// A [KITÖLTENDŐ] jelölésű helyeken jogi/üzemeltetői döntés kell. Amíg ezek
// nincsenek kitöltve, a tájékoztató nem tekinthető véglegesnek.
const KITOLTENDO =
  "inline-block rounded bg-amber-300/20 px-1.5 py-0.5 font-semibold text-amber-100";

function Szakasz({ cim, children }) {
  return (
    <section className="mt-8">
      <h2 className="font-serif text-xl text-white">{cim}</h2>
      <div className="mt-3 space-y-3 text-sm leading-6 text-slate-300">
        {children}
      </div>
    </section>
  );
}

export default function AdatkezelesPage() {
  return (
    <main className="career-shell min-h-screen">
      <div className="mx-auto max-w-3xl px-5 py-12 sm:px-8">
        <Link
          href="/"
          className="text-xs font-semibold text-slate-400 hover:text-amber-100"
        >
          ← Vissza a kezdőoldalra
        </Link>

        <h1 className="mt-6 font-serif text-3xl text-white">
          Adatkezelési tájékoztató
        </h1>
        <p className="mt-2 text-xs text-slate-500">
          Változat: {VERZIO}
        </p>

        <Szakasz cim="1. Ki kezeli az adataidat">
          <p>
            Az adatkezelő: <span className={KITOLTENDO}>[KITÖLTENDŐ: név]</span>,
            elérhetőség: <span className={KITOLTENDO}>[KITÖLTENDŐ: e-mail]</span>,
            székhely: <span className={KITOLTENDO}>[KITÖLTENDŐ: cím]</span>.
          </p>
        </Szakasz>

        <Szakasz cim="2. Milyen adatot kezelünk">
          <ul className="list-disc space-y-1.5 pl-5">
            <li>Fiókadat: e-mail cím, keresztnév.</li>
            <li>
              Önéletrajz: a feltöltött PDF és a belőle kinyert, általad
              jóváhagyott szöveg.
            </li>
            <li>
              Karrierprofil: célmunkakör, készségek, tapasztalat, helyszín,
              korlátok — kizárólag amit te adsz meg és erősítesz meg.
            </li>
            <li>Flow-val folytatott beszélgetésed.</li>
            <li>
              A folyamat állapota és eseménynaplója (mikor mit hagytál jóvá).
            </li>
          </ul>
        </Szakasz>

        <Szakasz cim="3. Miért kezeljük">
          <p>
            A szolgáltatás nyújtásához: önéletrajz-elemzéshez, piaci
            összevetéshez, álláskereséshez és pályázati anyagok
            elkészítéséhez. Jogalap: a veled kötött szerződés teljesítése,
            illetve az önéletrajz és a beszélgetés külső feldolgozása
            tekintetében a hozzájárulásod.
          </p>
        </Szakasz>

        <Szakasz cim="4. Kihez kerülnek az adataid">
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong className="text-slate-100">Supabase</strong> — adatbázis
              és fájltárolás.
            </li>
            <li>
              <strong className="text-slate-100">Google (Gemini)</strong> — a
              Flow-válaszok és a szövegelemzés elkészítéséhez a beszélgetésed
              és az önéletrajzod szövege ide kerül feldolgozásra.
            </li>
            <li>
              <strong className="text-slate-100">Vercel</strong> és{" "}
              <strong className="text-slate-100">Render</strong> — a weboldal
              és a háttérszolgáltatás üzemeltetése.
            </li>
          </ul>
          <p>
            Adataidat nem adjuk el, és nem használjuk hirdetési célra.
          </p>
        </Szakasz>

        <Szakasz cim="5. Meddig őrizzük">
          <p>
            <span className={KITOLTENDO}>
              [KITÖLTENDŐ: megőrzési idő fiókadatra, CV-re, beszélgetésre]
            </span>{" "}
            A fiókod törlésekor az adataid törlődnek, kivéve amit jogszabály
            hosszabb ideig megőrizni rendel.
          </p>
        </Szakasz>

        <Szakasz cim="6. Milyen jogaid vannak">
          <p>
            Kérheted az adataidhoz való hozzáférést, azok helyesbítését,
            törlését, a kezelés korlátozását, és tiltakozhatsz a kezelés
            ellen. A hozzájárulásodat bármikor visszavonhatod — ez a
            visszavonás előtti kezelést nem érinti.
          </p>
          <p>
            Törlési kérelem:{" "}
            <span className={KITOLTENDO}>[KITÖLTENDŐ: e-mail cím]</span>. Panasszal
            a Nemzeti Adatvédelmi és Információszabadság Hatósághoz (NAIH)
            fordulhatsz.
          </p>
        </Szakasz>

        <Szakasz cim="7. Különleges adatok">
          <p>
            A jóllét- és kiégés-kérdőív válaszai egészségi állapotra utaló,
            különleges adatnak minősülhetnek. Ezeket kizárólag külön, kifejezett
            hozzájárulásoddal kezeljük, és a kitöltés önkéntes — enélkül is
            használhatod a szolgáltatás többi részét.
          </p>
        </Szakasz>

        <Szakasz cim="8. Automatizált döntéshozatal">
          <p>
            A rendszer nem hoz rólad automatizált döntést. Az illeszkedési
            pontszámokat és rangsorokat program számolja mért adatokból, de
            ezek javaslatok: minden lépést te hagysz jóvá, és a pályázatot te
            adod be.
          </p>
        </Szakasz>
      </div>
    </main>
  );
}
