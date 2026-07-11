export function NoAccess({ userName }: { userName: string }) {
  return (
    <div className="no-access">
      <h2>No access</h2>
      <p>
        Sorry{userName ? ` ${userName}` : ''} — we couldn't match your account to an NV
        member, so the skill query tool has nothing to show you.
      </p>
      <p className="dim">If you think this is a mistake, ask in #it-helpdesk.</p>
    </div>
  )
}
