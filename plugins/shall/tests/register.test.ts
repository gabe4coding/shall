import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

import type { HookOutput } from '../hooks/register'

const ASK = {
  model: 'claude-haiku-5-5',
  timeout_ms: 8000,
  requests: [{ key: 'k1', system: 'SYSTEM', prompt: 'PROMPT', max_tokens: 88 }],
}

const DENY: HookOutput = {
  hookSpecificOutput: { permissionDecision: 'deny', permissionDecisionReason: 'shall: breaks JRFC-0012.1' },
}

// `bin/shall-hook` as the module runs it: `answer` gets each event it was sent.
function shallHook(on: On, answer: (event: Record<string, unknown>) => HookOutput, sent: Record<string, unknown>[] = []) {
  on('process.run', ($, e) => {
    const event = JSON.parse(e.init?.stdin ?? '{}') as Record<string, unknown>
    sent.push({ ...event, argv: e.argv })
    const out = answer(event)
    const stdout = Object.keys(out).length > 0 ? JSON.stringify(out) : ''
    return { value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  return sent
}

function session(on: On) {
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.id', () => ({ value: 's1' }))
  on('tool.call', () => ({ result: 'ran' }))
}

function reply(text: string) {
  return { value: { isAnswered: true, text, usage: { input_tokens: 1, output_tokens: 1 } } } as never
}

test('asks the model for the prompts shall needs, then applies the decision with the replies', async ($, on) => {
  session(on)
  const models: Record<string, unknown>[] = []
  on('model.complete', ($, e) => {
    models.push({ model: e.model, system: e.system, prompt: e.prompt, maxTokens: e.maxTokens })
    return reply('1: yes')
  })
  const sent = shallHook(on, event => (event.shall_replies ? DENY : { shall_ask: ASK }))
  const ran = await $.tool.call({ tool: 'Bash', command: 'git push origin main' })
  expect(ran.deny).toContain('JRFC-0012.1')
  expect(models).toEqual([{ model: 'claude-haiku-5-5', system: 'SYSTEM', prompt: 'PROMPT', maxTokens: 88 }])
  expect(sent.length).toBe(2)
  expect(sent[0]).toMatchObject({
    hook_event_name: 'PreToolUse', session_id: 's1', cwd: '/repo', tool_name: 'Bash',
    tool_input: { command: 'git push origin main' }, shall_judge: 'claude',
  })
  expect(String((sent[0]?.argv as string[])[0])).toContain('/bin/shall-hook')
  expect(sent[1]?.shall_replies).toEqual({ k1: '1: yes' })
})

test('runs shall once when it decides without the model (Jev key, cache, code checks)', async ($, on) => {
  session(on)
  let asked = 0
  on('model.complete', () => {
    asked += 1
    return reply('1: yes')
  })
  const sent = shallHook(on, () => DENY)
  const ran = await $.tool.call({ tool: 'Bash', command: 'git push origin main' })
  expect(ran.deny).toContain('JRFC-0012.1')
  expect(sent.length).toBe(1)
  expect(asked).toBe(0)
})

test('fails open to the code checks when the model does not answer', async ($, on) => {
  session(on)
  on('model.complete', () => ({ value: { isAnswered: false, reason: 'api-error', status: 529, error: 'overloaded' } }) as never)
  const sent = shallHook(on, event => (event.shall_replies ? DENY : { shall_ask: ASK }))
  const ran = await $.tool.call({ tool: 'Bash', command: 'git push origin main' })
  expect(ran).toEqual({ result: 'ran' })
  expect(sent.length).toBe(1)
})

test('fails open when shall prints no JSON', async ($, on) => {
  session(on)
  on('process.run', () => ({ value: { exitCode: 1, stdout: 'Traceback', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  const ran = await $.tool.call({ tool: 'Bash', command: 'ls' })
  expect(ran.isError).toBeUndefined()
})

test('starts no process for a tool the hooks do not check', async ($, on) => {
  session(on)
  const sent = shallHook(on, () => DENY)
  const ran = await $.tool.call({ tool: 'Read', file_path: '/repo/a.py' })
  expect(ran.isError).toBeUndefined()
  expect(sent.length).toBe(0)
})

test('gives the model the warning shall writes after a write', async ($, on) => {
  session(on)
  const warn: HookOutput = {
    hookSpecificOutput: { additionalContext: 'shall: the code just written may break JRFC-0006.1' },
    systemMessage: 'shall: a.py: JRFC-0006.1',
  }
  const sent = shallHook(on, event => (event.hook_event_name === 'PostToolUse' ? warn : {}))
  const ran = await $.tool.call({ tool: 'Write', file_path: '/repo/a.py', content: 'x' })
  expect(ran.context).toEqual(['shall: the code just written may break JRFC-0006.1'])
  expect(sent.map(event => event.hook_event_name)).toEqual(['PreToolUse', 'PostToolUse'])
})

test('checks no written code when the write failed or was refused', async ($, on) => {
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.id', () => ({ value: 's1' }))
  on('tool.call', () => ({ deny: 'refused by the person' }))
  const sent = shallHook(on, () => ({}))
  const ran = await $.tool.call({ tool: 'Write', file_path: '/repo/a.py', content: 'x' })
  expect(ran.deny).toBe('refused by the person')
  expect(sent.map(event => event.hook_event_name)).toEqual(['PreToolUse'])
})
