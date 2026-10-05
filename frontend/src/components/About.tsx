const PROJECTS = [
  {
    name: "Who's Knocking? (this site)",
    href: "https://github.com/TrevorvaughanDEV/devops-project",
    link: "Source on GitHub",
    body: "An SSH honeypot I wrote in Python, streaming real attacks to a React map. FastAPI, SQLite, Docker, Nginx, Terraform on Azure, and pull-based deploys that test, health-check and roll back on their own.",
  },
  {
    name: "Server monitor",
    href: "https://monitor.trevorvaughan.dev",
    link: "monitor.trevorvaughan.dev",
    body: "The first version of this site: a Flask dashboard of live CPU, memory and disk use with accounts and alerts. Built on AWS EC2, then moved to Azure when the free plan ended.",
  },
  {
    name: "Weekly attack report",
    href: "/report",
    link: "Read this week's report",
    body: "A summary written automatically from the honeypot's data each week: what was tried, from where, and how it compares with the week before.",
  },
];

export function About() {
  return (
    <section id="about" className="band about" aria-labelledby="about-title">
      <div className="about-intro">
        <h2 id="about-title">Built by Trevor Vaughan</h2>
        <p>
          I'm a Network Engineering student at TU Dublin, working towards cloud, DevOps and
          security engineering. I built and run everything on this site myself: the honeypot, the API,
          the map, the Azure server and the pipeline that deploys it.
        </p>
        <p>I'm open to internships in cloud, DevOps, networking and security.</p>
        <p className="about-links">
          <a href="https://www.linkedin.com/in/trevor-vaughan-1739912ab/">LinkedIn</a>
          <a href="https://github.com/TrevorvaughanDEV">GitHub</a>
        </p>
      </div>
      <ul className="projects">
        {PROJECTS.map((p) => (
          <li key={p.name}>
            <h3>{p.name}</h3>
            <p>{p.body}</p>
            <a href={p.href}>{p.link}</a>
          </li>
        ))}
      </ul>
    </section>
  );
}
