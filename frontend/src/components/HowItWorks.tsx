const STEPS = [
  {
    title: "A fake front door",
    body: "A small SSH server I wrote in Python listens on the open internet. It looks like a normal Ubuntu box and writes down the username and password of every login attempt. Almost all of them are refused.",
  },
  {
    title: "A fake shell",
    body: "The very worst passwords, like 123456, \"work\". The bot lands in an imitation Linux terminal that answers like the real thing, so it carries on with its script. Every command is recorded, but nothing ever runs and nothing is ever downloaded.",
  },
  {
    title: "Who is it?",
    body: "Each address is looked up in the DB-IP databases for its country, city and network. Opening an address also checks it against AbuseIPDB, where other people report attackers.",
  },
  {
    title: "Spotting botnets",
    body: "Machines that work through the same password list, with the same software, are grouped together. Passwords every bot tries are ignored, so the groups are linked by the unusual ones, even when a botnet splits its list between machines.",
  },
  {
    title: "Stored and streamed",
    body: "Attempts and shell commands go into SQLite and straight out to every open browser over a WebSocket, so the map and the terminal move the moment a bot does. FastAPI serves the API; this page is React.",
  },
  {
    title: "It deploys itself",
    body: "Every push to GitHub is linted, tested and security-scanned. The Azure server checks for new versions every two minutes, runs the tests again, swaps in the new build and rolls back on its own if it fails a health check. Terraform describes the infrastructure.",
  },
];

export function HowItWorks() {
  return (
    <ol className="how">
      {STEPS.map((s) => (
        <li key={s.title}>
          <h3>{s.title}</h3>
          <p>{s.body}</p>
        </li>
      ))}
    </ol>
  );
}
