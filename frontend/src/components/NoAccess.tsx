export function NoAccess({ userName }: { userName: string }) {
  return (
    <div className="no-access">
      <h2>No access</h2>
      <p>
        Sorry{userName ? ` ${userName}` : ''} — the skill query tool is limited to High
        Command and the Doctrine team.
      </p>
      <p className="dim">If you think you should have access, ask in #it-helpdesk.</p>
    </div>
  )
}
