import { Client } from '@atproto/lex'
import { PasswordSession } from '@atproto/lex-password-session'
import { SpaceClient, listSpaces, personalspace } from '@atproto/lex-space'
import * as dotenv from 'dotenv'
import * as community from './lexicons/community.js'

dotenv.config()

export const calendarType = community.lexicon.calendar.collection.main
export const event = community.lexicon.calendar.event

export async function login() {
  const session = await PasswordSession.login({
    service: process.env.PDS_URL!,
    identifier: process.env.HANDLE!,
    password: process.env.PASSWORD!,
  })
  return new Client(session)
}

export async function openCalendar(client: Client) {
  const { spaces } = await client.call(listSpaces, {
    spaceType: calendarType.nsid,
    spaceDid: client.did,
  })

  if (!spaces.some((s) => s.space.endsWith('/personal'))) {
    return SpaceClient.createSpace(client.agent, calendarType, {
      skey: 'personal',
      policy: personalspace.policy.$build({}),
    })
  }

  return SpaceClient.openSpace(
    calendarType,
    { authority: client.did, skey: 'personal' },
    { agent: client.agent },
  )
}
