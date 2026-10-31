"""Feed e pagine di esempio per i test (inventati)."""

LONG = " ".join(["Questo è un paragrafo dell'articolo con abbastanza parole per sembrare vero."] * 30)

RSS_EXCERPT = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>Orbita</title>
  <link>https://orbita.example/</link>
  <item>
    <title>Perché le missioni lunari puntano al polo sud</title>
    <link>https://orbita.example/luna-polo-sud?utm_source=rss</link>
    <guid>https://orbita.example/?p=1</guid>
    <pubDate>Sat, 31 Oct 2026 08:00:00 GMT</pubDate>
    <category>Luna</category>
    <description><![CDATA[<p>Ghiaccio nei crateri in ombra perenne.</p> <a href="https://orbita.example/luna#comments">12 commenti</a>]]></description>
    <media:thumbnail url="https://orbita.example/img/luna.jpg"/>
  </item>
  <item>
    <title>Come si misura una galassia</title>
    <link>https://orbita.example/galassie</link>
    <guid>https://orbita.example/?p=2</guid>
    <pubDate>Fri, 30 Oct 2026 08:00:00 GMT</pubDate>
    <description>Parallasse, Cefeidi e redshift.</description>
  </item>
</channel>
</rss>"""

ATOM_FULL = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Bit &amp; Byte</title>
  <link href="https://bitebyte.example/"/>
  <id>urn:bitebyte</id>
  <updated>2026-10-31T09:00:00Z</updated>
  <entry>
    <title>Le PWA su iPhone</title>
    <link href="/pwa-iphone"/>
    <id>urn:bitebyte:1</id>
    <updated>2026-10-31T09:00:00Z</updated>
    <author><name>Redazione</name></author>
    <content type="html"><![CDATA[<h1>Le PWA su iPhone</h1><p>{LONG}</p><script>alert(1)</script><img src="/pixel.gif" width="1" height="1"><img src="/foto.jpg" alt="foto">]]></content>
  </entry>
</feed>"""

YOUTUBE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>Cronache Spaziali</title>
 <link rel="alternate" href="https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv"/>
 <entry>
  <id>yt:video:vid12345678</id>
  <yt:videoId>vid12345678</yt:videoId>
  <title>Come atterra un razzo</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=vid12345678"/>
  <author><name>Cronache Spaziali</name></author>
  <published>2026-10-31T07:00:00+00:00</published>
  <media:group>
   <media:title>Come atterra un razzo</media:title>
   <media:thumbnail url="https://i.ytimg.com/vi/vid12345678/hqdefault.jpg" width="480" height="360"/>
   <media:description>Motori riaccesi in discesa.</media:description>
  </media:group>
 </entry>
</feed>"""

SITE_PAGE = """<!doctype html><html><head><title>Orbita</title>
<link rel="alternate" type="application/rss+xml" title="Orbita · tutte le notizie" href="/feed.xml">
<link rel="alternate" type="application/rss+xml" title="Orbita · commenti" href="/comments/feed">
<link rel="alternate" type="application/atom+xml" title="Approfondimenti" href="https://orbita.example/approfondimenti.atom">
</head><body><h1>Orbita</h1></body></html>"""

PLAIN_PAGE = "<!doctype html><html><head><title>Senza feed</title></head><body><p>Niente feed qui.</p></body></html>"

YOUTUBE_CHANNEL_PAGE = """<!doctype html><html><head>
<meta itemprop="identifier" content="UCabcdefghijklmnopqrstuv">
</head><body>canale</body></html>"""

ARTICLE_PAGE = f"""<!doctype html><html><head><title>Luna</title>
<meta property="og:image" content="https://orbita.example/img/og.jpg"></head>
<body><nav>Menu Home Contatti</nav><article><h1>Perché le missioni lunari puntano al polo sud</h1>
<p>{LONG}</p><p>Secondo paragrafo con <a href="/altro">un link</a>.</p></article>
<div class="comments"><p>Commento di un lettore</p></div><footer>Copyright</footer></body></html>"""

OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0"><head><title>Export</title></head><body>
  <outline text="Spazio" title="Spazio">
    <outline type="rss" text="Orbita" title="Orbita" xmlUrl="https://orbita.example/feed.xml" htmlUrl="https://orbita.example/"/>
    <outline text="Sotto">
      <outline type="rss" text="Cronache" xmlUrl="https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnopqrstuv"/>
    </outline>
  </outline>
  <outline type="rss" text="Bit &amp; Byte" xmlUrl="https://bitebyte.example/atom.xml"/>
  <outline type="rss" text="Rotto" xmlUrl="javascript:alert(1)"/>
</body></opml>"""
