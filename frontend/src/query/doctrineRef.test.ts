import { describe, expect, it } from 'vitest'
import type { DoctrineFitOut } from '../api'
import {
  decodeDoctrineRef,
  doctrineLabel,
  doctrineOptions,
  encodeDoctrineRef,
  fitOptions,
  findFit,
  roleOptions,
  shipOptions,
  type DoctrineRef,
} from './doctrineRef'

function fit(
  doctrine: string,
  role: string,
  ship_type: string,
  fit_name: string,
  yellow = 10,
  green = 20,
): DoctrineFitOut {
  return { doctrine, role, ship_type, fit_name, yellow_skill_count: yellow, green_skill_count: green }
}

const FITS: DoctrineFitOut[] = [
  fit('BDA', 'Mainline', 'Legion', 'DPS'),
  fit('BDA', 'Mainline', 'Loki', 'DPS'),
  fit('BDA', 'Logi', 'Guardian', 'Standard'),
  fit('Armor', 'DPS', 'Megathron', ''),
]

describe('doctrineRef codec', () => {
  it('round-trips a ref', () => {
    const ref: DoctrineRef = {
      doctrine: 'STRAT',
      role: 'Logi',
      ship_type: 'Tengu',
      fit_name: 'Logi Tengu / X',
      tier: 'yellow',
    }
    expect(decodeDoctrineRef(encodeDoctrineRef(ref))).toEqual(ref)
  })

  it('returns null for garbage', () => {
    expect(decodeDoctrineRef('!!!')).toBeNull()
  })
})

describe('cascading option helpers', () => {
  it('lists distinct doctrines sorted', () => {
    expect(doctrineOptions(FITS)).toEqual(['Armor', 'BDA'])
  })

  it('lists roles within a doctrine', () => {
    expect(roleOptions(FITS, 'BDA')).toEqual(['Logi', 'Mainline'])
  })

  it('lists ships within a doctrine+role', () => {
    expect(shipOptions(FITS, 'BDA', 'Mainline')).toEqual(['Legion', 'Loki'])
  })

  it('lists fit names within a doctrine+role+ship', () => {
    expect(fitOptions(FITS, 'BDA', 'Mainline', 'Legion')).toEqual(['DPS'])
    // Empty fit_name is preserved as a real (single) option.
    expect(fitOptions(FITS, 'Armor', 'DPS', 'Megathron')).toEqual([''])
  })

  it('finds a fit by identity', () => {
    const found = findFit(FITS, {
      doctrine: 'BDA',
      role: 'Logi',
      ship_type: 'Guardian',
      fit_name: 'Standard',
    })
    expect(found?.green_skill_count).toBe(20)
    expect(
      findFit(FITS, { doctrine: 'BDA', role: 'Logi', ship_type: 'Guardian', fit_name: 'X' }),
    ).toBeNull()
  })
})

describe('doctrineLabel', () => {
  it('joins identity and tier, dropping empty fit name', () => {
    expect(
      doctrineLabel({ doctrine: 'BDA', role: 'Mainline', ship_type: 'Legion', fit_name: 'DPS', tier: 'green' }, 53),
    ).toBe('BDA / Mainline / Legion / DPS — green (53 skills)')
    expect(
      doctrineLabel({ doctrine: 'Armor', role: 'DPS', ship_type: 'Megathron', fit_name: '', tier: 'yellow' }, 30),
    ).toBe('Armor / DPS / Megathron — yellow (30 skills)')
  })
})
