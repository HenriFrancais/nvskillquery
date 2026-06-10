import { describe, expect, it } from 'vitest'
import { groupsToParam, parseGroupsParam } from './groups'

const ALL = ['Home', 'Strat', 'Farm', 'Alpha']

describe('groupsToParam', () => {
  it('omits the param when all groups are selected', () => {
    expect(groupsToParam(new Set(ALL), ALL)).toBeNull()
  })

  it('serialises a subset in vocabulary order', () => {
    expect(groupsToParam(new Set(['Farm', 'Home']), ALL)).toBe('Home,Farm')
  })

  it('treats an empty selection as nothing to share', () => {
    expect(groupsToParam(new Set(), ALL)).toBeNull()
  })
})

describe('parseGroupsParam', () => {
  it('returns all groups when the param is absent', () => {
    expect(parseGroupsParam(null, ALL)).toEqual(new Set(ALL))
    expect(parseGroupsParam('', ALL)).toEqual(new Set(ALL))
  })

  it('parses a subset and drops unknown names', () => {
    expect(parseGroupsParam('Home,Nope,Strat', ALL)).toEqual(new Set(['Home', 'Strat']))
  })

  it('falls back to all groups when nothing valid remains', () => {
    expect(parseGroupsParam('Nope,Wrong', ALL)).toEqual(new Set(ALL))
  })
})
