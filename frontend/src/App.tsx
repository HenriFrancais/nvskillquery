import { NoAccess } from './components/NoAccess'
import { useMe } from './hooks/useMe'
import { SkillQuery } from './views/SkillQuery'

export function App() {
  const { me, error } = useMe()

  if (error) {
    return <div className="centered dim">Failed to load identity: {error}</div>
  }
  if (me === null) {
    return <div className="centered dim">Loading…</div>
  }
  if (!me.can_query) {
    return <NoAccess userName={me.user_name} />
  }
  return <SkillQuery />
}
