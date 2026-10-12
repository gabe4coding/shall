// The tool-call hooks of the shall plugin, with Claude as the judge when there is no Jev key.
//
// `bin/shall-hook` (Python) stays the pipeline and makes every decision. This module only
// carries the model: it sends the event with `shall_judge: "claude"`; without TYPESAFE_API_KEY
// shall answers with the prompts it needs (`shall_ask`); the module asks the model through the
// session's own client (`$.model.complete`, no tools) and sends the event again with the
// replies (`shall_replies`). With the key, shall asks Jev and never returns `shall_ask`.
// The Stop review stays a command hook in hooks.json.
//
// `tool.call` and `tool.check`, not `classic.PreToolUse`: the built-in security module bypasses
// a user-tier plugin's classic tool hooks (debug log: "classic.PreToolUse bypassed by
// cc-plugin-sec-default (tier user)"). Before the call: deny in `tool.call`, ask in
// `tool.check`. After a write: the warnings ride on the result as `context`, which the model
// reads as it reads a PostToolUse hook's.
//
// Fail-open, as the command hooks: a failed run, an unanswered model or a reply with no
// answers lets the call run with the decision of the code checks alone.

import type { EngineInterface, Register } from 'claude-code'

// The tools the command hooks matched (`hooks.pre_matcher`, `hooks.code_tools`): other
// calls never start the process.
const PRE_TOOLS = /^(Bash|Write|Edit|MultiEdit|NotebookEdit|mcp__.*)$/
const CODE_TOOLS = /^(Write|Edit|MultiEdit|NotebookEdit)$/

// The process runs twice per judged call (prompts, then decision), each about 0.5 s.
const RUN_MS = 20000

type Ask = {
  model: string
  timeout_ms: number
  requests: { key: string; system: string; prompt: string; max_tokens: number }[]
}

// What `shall hook` prints: a classic hook output, plus `shall_ask` for this module.
export type HookOutput = {
  hookSpecificOutput?: {
    permissionDecision?: 'deny' | 'ask'
    permissionDecisionReason?: string
    additionalContext?: string
  }
  systemMessage?: string
  shall_ask?: Ask
}

type HookEvent = Record<string, unknown> & { hook_event_name: string; cwd: string }

async function runHook($: EngineInterface, event: HookEvent): Promise<HookOutput> {
  const ran = await $.process
    .run([`${$.plugin.root}/bin/shall-hook`], { cwd: event.cwd, stdin: JSON.stringify(event), timeoutMs: RUN_MS })
    .catch(() => null)
  // exit 3 (Jev failed) still prints the decision of the code checks
  const text = ran?.stdout.trim() ?? ''
  if (text === '') return {}
  try {
    const out: unknown = JSON.parse(text)
    return typeof out === 'object' && out !== null ? (out as HookOutput) : {}
  } catch {
    return {}
  }
}

// One model call per request of `shall_ask`; a request with no answer is left out.
async function askModel($: EngineInterface, ask: Ask): Promise<Record<string, string>> {
  const replies: Record<string, string> = {}
  await Promise.all(
    ask.requests.map(async r => {
      const reply = await $.model
        .complete({
          model: ask.model,
          system: r.system,
          prompt: r.prompt,
          maxTokens: r.max_tokens,
          effort: 'low',
          timeoutMs: ask.timeout_ms,
        })
        .catch(() => null)
      if (reply?.isAnswered) replies[r.key] = reply.text
    }),
  )
  return replies
}

// The decision for one event: shall's, with the model's answers when it needed them.
export async function judge($: EngineInterface, event: HookEvent): Promise<HookOutput> {
  const first = await runHook($, { ...event, shall_judge: 'claude' })
  const { shall_ask: ask, ...codeOnly } = first
  if (ask === undefined || ask.requests.length === 0) return codeOnly
  const replies = await askModel($, ask)
  if (Object.keys(replies).length === 0) return codeOnly
  const { shall_ask: _, ...decided } = await runHook($, { ...event, shall_judge: 'claude', shall_replies: replies })
  return decided
}

// The reason of each call shall wants approved, by tool_use_id: `tool.call` judges the call,
// `tool.check` (the engine's permission decision, inside `next`) puts it to the session's
// decider: the dialog, or the classifier in auto mode.
const asks = new Map<string, string>()

export const register: Register = on => {
  on('tool.call', async ($, e, next) => {
    if (!PRE_TOOLS.test(e.tool)) return next(e)
    const { tool, tool_use_id: id, agentId: _agent, requestMeta: _meta, ...toolInput } = e
    const [cwd, sessionId] = await Promise.all([$.session.cwd(), $.session.id()])
    const base = { session_id: sessionId, cwd, tool_name: tool, tool_input: toolInput, tool_use_id: id }
    const pre = await judge($, { ...base, hook_event_name: 'PreToolUse' })
    if (pre.systemMessage) $.ui.log(pre.systemMessage)
    const decided = pre.hookSpecificOutput ?? {}
    const reason = decided.permissionDecisionReason ?? 'shall: engineering standards'
    if (decided.permissionDecision === 'deny') return { deny: reason }
    if (decided.permissionDecision === 'ask' && id !== undefined) asks.set(id, reason)
    const ran = await next(e).finally(() => id !== undefined && asks.delete(id))
    const context = decided.additionalContext ? [decided.additionalContext] : []
    if (CODE_TOOLS.test(tool) && ran.deny === undefined && ran.isError !== true) {
      // the code just written: warnings only, as the PostToolUse command hook gave them. The
      // call has run: a failure here must not reach `.catch`, which would run it again.
      const post = await judge($, { ...base, hook_event_name: 'PostToolUse' }).catch((): HookOutput => ({}))
      if (post.systemMessage) $.ui.log(post.systemMessage)
      if (post.hookSpecificOutput?.additionalContext) context.push(post.hookSpecificOutput.additionalContext)
    }
    if (ran.deny !== undefined || context.length === 0) return ran
    return { ...ran, context: [...(ran.context ?? []), ...context] }
  }).catch(($, e, next) => next(e)) // fail-open: the call runs unchecked

  // A call shall puts to the person: ask, unless the engine already refuses it.
  on('tool.check', async ($, e, next) => {
    const reason = e.tool_use_id === undefined ? undefined : asks.get(e.tool_use_id)
    if (reason === undefined) return next(e)
    const below = await next(e)
    return below.decision === 'deny' ? below : { decision: 'ask', reason }
  })
}
