// Captures navigateur de la préprod, sans agent : ce que recette-live relève, préparé à l'avance.
// Lancé par le serveur de l'application Audit (Node, Chromium et Playwright dans le conteneur),
// pour que la recette puisse se finir sur un poste sans navigateur piloté ni Node.
//
//   node captures.mjs DOSSIER
//
// Pour chaque gabarit et page stratégique du profil, à 360 puis 1280 px :
//   - capture de la partie visible : captures/serveur/<nom>-<largeur>.png ;
//   - à 360 px, menu ouvert si un bouton de menu est trouvé : <nom>-360-menu.png ;
//   - relevés (lecture seule) : viewport, défilement horizontal, liens du menu, fil d'Ariane,
//     éléments fixes qui couvrent plus de 30 % de l'écran, title, canonical, H1, premier paragraphe.
// Tout va dans DOSSIER/captures/serveur/releves.json. Le HTML rendu est dans captures/serveur/html/.
// L'accès à la préprod vient de acces-preprod.local.json (jamais écrit dans les relevés).
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
function chargerPlaywright() {
  const pistes = [process.env.PLAYWRIGHT_CORE, 'playwright-core', 'playwright',
    '/usr/local/lib/node_modules/@playwright/mcp/node_modules/playwright-core'].filter(Boolean);
  for (const p of pistes) {
    try { return require(p); } catch { /* suivante */ }
  }
  console.error('ECHEC: playwright-core introuvable (PLAYWRIGHT_CORE=chemin du module).');
  process.exit(2);
}

const dossier = process.argv[2];
if (!dossier || !fs.existsSync(path.join(dossier, 'profil.json'))) {
  console.error('Usage : node captures.mjs DOSSIER (avec profil.json)');
  process.exit(2);
}
const lireJson = (p, defaut) => { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return defaut; } };
const profil = lireJson(path.join(dossier, 'profil.json'), {});
const acces = lireJson(path.join(dossier, 'acces-preprod.local.json'), null);

const pages = [];
const vues = new Set();
const ajouter = (nom, url, origine) => {
  if (!url || vues.has(url)) return;
  vues.add(url);
  const slug = String(nom || 'page').normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'page';
  pages.push({ nom: `${String(pages.length + 1).padStart(2, '0')}-${slug}`, libelle: nom, url, origine });
};
for (const g of profil.gabarits || []) ajouter(g.type, g.url, 'gabarit');
for (const p of profil.pages_strategiques || []) ajouter(p.nom, p.url, 'page stratégique');
if (!pages.length && profil.preprod) ajouter('accueil', profil.preprod.replace(/\/?$/, '/'), 'gabarit');

const sortie = path.join(dossier, 'captures', 'serveur');
fs.mkdirSync(path.join(sortie, 'html'), { recursive: true });

const options = { ignoreHTTPSErrors: profil.ssl_verifie === false };
if (acces && acces.identifiant) {
  options.httpCredentials = { username: acces.identifiant, password: acces.mot_de_passe || '',
    origin: new URL(acces.preprod || profil.preprod).origin };
}
if (acces && acces.en_tetes_supplementaires && Object.keys(acces.en_tetes_supplementaires).length) {
  options.extraHTTPHeaders = acces.en_tetes_supplementaires;
}

// Relevés faits dans la page, en lecture seule.
function relever() {
  const texte = (e) => (e && e.textContent || '').replace(/\s+/g, ' ').trim();
  const liens = (racine) => racine ? [...racine.querySelectorAll('a[href]')]
    .map((a) => ({ texte: texte(a).slice(0, 80), href: a.href })).filter((l) => l.texte || l.href).slice(0, 150) : [];
  const menu = document.querySelector('header nav, nav[role="navigation"], [role="navigation"], nav, header');
  const ariane = document.querySelector('[aria-label*="readcrumb" i], [class*="breadcrumb" i], [id*="breadcrumb" i], nav[aria-label*="ariane" i], [class*="ariane" i]');
  const surface = innerWidth * innerHeight;
  const fixes = [...document.querySelectorAll('body *')].filter((e) => {
    const s = getComputedStyle(e);
    if (!['fixed', 'sticky'].includes(s.position) || s.display === 'none' || s.visibility === 'hidden') return false;
    const r = e.getBoundingClientRect();
    const visible = Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0)) *
      Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
    return visible / surface > 0.3;
  }).slice(0, 10).map((e) => {
    const r = e.getBoundingClientRect();
    return { balise: e.tagName.toLowerCase(), id: e.id || '', classe: String(e.className || '').slice(0, 120),
      texte: texte(e).slice(0, 160), largeur: Math.round(r.width), hauteur: Math.round(r.height),
      cookies: /cookie|consent|rgpd|gdpr|tarteaucitron|axeptio|didomi|onetrust/i.test(e.id + ' ' + e.className + ' ' + texte(e).slice(0, 300)) };
  });
  const p = [...document.querySelectorAll('main p, article p, p')].find((x) => texte(x).length > 40);
  return {
    viewport: document.querySelector('meta[name="viewport"]')?.getAttribute('content') ?? null,
    defilement_horizontal: document.documentElement.scrollWidth > innerWidth,
    largeur_document: document.documentElement.scrollWidth,
    title: document.title,
    canonical: document.querySelector('link[rel="canonical"]')?.href ?? null,
    h1: [...document.querySelectorAll('h1')].map(texte).slice(0, 5),
    premier_paragraphe: p ? texte(p).slice(0, 300) : null,
    menu_principal: liens(menu),
    fil_ariane: ariane ? { elements: [...ariane.querySelectorAll('a, span, li')].map(texte).filter(Boolean).slice(0, 12),
      dernier_cliquable: !!ariane.querySelector('li:last-child a') } : null,
    fixes_plus_30_pourcent: fixes,
  };
}

// Bouton de menu mobile : on clique sur le premier candidat visible (aucune saisie, aucun envoi).
const CANDIDATS_MENU = ['button[aria-controls][aria-expanded="false"]', '[class*="hamburger" i]', '[class*="burger" i]',
  '[class*="menu-toggle" i]', '[class*="nav-toggle" i]', 'button[aria-label*="menu" i]', '[class*="toggle" i][class*="menu" i]',
  '.elementor-menu-toggle', '.et_mobile_nav_menu', '.mobile-menu-toggle'];

const { chromium } = chargerPlaywright();
const navigateur = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || undefined,
  args: ['--no-sandbox'] });
const releves = { cree_le: new Date().toISOString(), outil: 'captures.mjs (serveur)', pages: [] };
try {
  for (const pg of pages) {
    const fiche = { nom: pg.libelle, url: pg.url, origine: pg.origine, largeurs: {} };
    for (const largeur of [360, 1280]) {
      const contexte = await navigateur.newContext({ ...options, viewport: { width: largeur, height: largeur === 360 ? 780 : 900 },
        isMobile: largeur === 360, hasTouch: largeur === 360, deviceScaleFactor: 1 });
      const page = await contexte.newPage();
      const v = {};
      try {
        const rep = await page.goto(pg.url, { waitUntil: 'load', timeout: 45000 });
        await page.waitForTimeout(2500); // pop-ins et contenus chargés après coup
        v.code = rep ? rep.status() : null;
        v.url_finale = page.url();
        const capture = `${pg.nom}-${largeur}.png`;
        await page.screenshot({ path: path.join(sortie, capture) });
        v.capture = `captures/serveur/${capture}`;
        Object.assign(v, await page.evaluate(relever));
        if (largeur === 1280) {
          const html = `${pg.nom}-rendu.html`;
          fs.writeFileSync(path.join(sortie, 'html', html), await page.content());
          v.html_rendu = `captures/serveur/html/${html}`;
        }
        if (largeur === 360) {
          for (const sel of CANDIDATS_MENU) {
            const bouton = page.locator(sel).first();
            if (await bouton.count() && await bouton.isVisible().catch(() => false)) {
              await bouton.click({ timeout: 5000 }).catch(() => {});
              await page.waitForTimeout(1200);
              const cap = `${pg.nom}-360-menu.png`;
              await page.screenshot({ path: path.join(sortie, cap) });
              v.menu_mobile = { bouton: sel, capture: `captures/serveur/${cap}`,
                liens_menu_ouvert: (await page.evaluate(relever)).menu_principal };
              break;
            }
          }
          if (!v.menu_mobile) v.menu_mobile = { bouton: null, note: 'aucun bouton de menu reconnu' };
        }
      } catch (e) {
        v.erreur = String(e.message || e).split('\n')[0].slice(0, 300);
      } finally {
        await contexte.close();
      }
      fiche.largeurs[largeur] = v;
    }
    releves.pages.push(fiche);
    console.log(`${pg.url} : ${Object.values(fiche.largeurs).map((x) => x.erreur ? 'erreur' : x.code).join(' / ')}`);
  }
} finally {
  await navigateur.close();
}
fs.writeFileSync(path.join(sortie, 'releves.json'), JSON.stringify(releves, null, 1));
console.log(JSON.stringify({ pages: releves.pages.length, dossier: 'captures/serveur' }));
