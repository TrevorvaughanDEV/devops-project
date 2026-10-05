const STEPS = [
  {
    title: "A fake front door",
    body: "A small SSH server I wrote in Python listens on the open internet. It looks like a normal Ubuntu box, accepts every login attempt, writes down the username and password, and refuses them all. Nobody ever gets a shell.",
  },
  {
    title: "Who is it?",
    body: "Each address is looked up in the DB-IP databases for its country, city and network. Opening an address also checks it against AbuseIPDB, where other people report attackers.",
  },
  {
    title: "Stored and streamed",
    body: "Attempts go into SQLite and straight out to every open browser over a WebSocket, so the map moves the moment a bot knocks. FastAPI serves the API; this page is React.",
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
