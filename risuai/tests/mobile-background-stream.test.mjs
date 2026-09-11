import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { stripTypeScriptTypes } from 'node:module';
import { join } from 'node:path';
import { test } from 'node:test';

// Exercise the actual patched upstream function without importing the entire UI.
const sourceDir = process.env.RISUAI_SOURCE_DIR;
assert.ok(sourceDir, 'Set RISUAI_SOURCE_DIR to the checkout with the patch stack applied');
const source = await readFile(join(sourceDir, 'src/ts/globalApi.svelte.ts'), 'utf8');
const start = source.indexOf('async function fetchViaProxyJobWs(');
assert.notEqual(start, -1);
const end = source.indexOf('\n/**', start);
assert.notEqual(end, -1);
const functionSource = stripTypeScriptTypes(source.slice(start, end));
const helpers = stripTypeScriptTypes(await readFile(join(sourceDir, 'src/ts/network/proxyJobWs.ts'), 'utf8'))
    .replace(/^export /gm, '');
const tick = () => new Promise(resolve => setTimeout(resolve, 10));

function fixture({ delayCreation = false } = {}) {
    class Page extends EventTarget {
        visibilityState = 'visible';
        browserFrozen = false;
        hide() {
            this.visibilityState = 'hidden';
            this.dispatchEvent(new Event('visibilitychange'));
        }
        freeze() {
            this.browserFrozen = true;
            this.dispatchEvent(new Event('freeze'));
        }
        showBeforeResume() {
            this.visibilityState = 'visible';
            this.dispatchEvent(new Event('visibilitychange'));
        }
        resume() {
            // Android dispatches lifecycle callbacks while synchronous socket
            // creation can still be rejected. Freezable tasks run afterwards.
            this.dispatchEvent(new Event('resume'));
            this.browserFrozen = false;
        }
    }
    const page = new Page();
    const sockets = [];
    const requests = [];
    const events = [];
    let rejectedConnections = 0;
    let releaseCreation;
    const creation = new Promise(resolve => { releaseCreation = resolve; });
    class Socket {
        readyState = 0;
        constructor(url) {
            this.url = url;
            sockets.push(this);
            if (page.browserFrozen) {
                rejectedConnections++;
                queueMicrotask(() => this.close());
                return;
            }
            queueMicrotask(() => {
                if (this.readyState !== 0) return;
                this.readyState = 1;
                this.onopen?.();
                const after = Number(new URL(url).searchParams.get('after') ?? 0);
                for (const event of events) {
                    if (event.sequence > after) this.deliver(event);
                }
            });
        }
        deliver(event) {
            if (this.readyState === 1) this.onmessage?.({ data: JSON.stringify(event) });
        }
        close() {
            if (this.readyState === 3) return;
            this.readyState = 3;
            queueMicrotask(() => this.onclose?.());
        }
    }
    const fetch = async (url, options) => {
        requests.push({ method: options.method, url });
        if (options.method === 'POST') {
            if (delayCreation) await creation;
            return Response.json({ jobId: 'one-generation' });
        }
        return new Response(null, { status: 204 });
    };
    const run = new Function(
        'document', 'WebSocket', 'fetch', 'location', 'getNodeServerProxyAuth',
        'getProxyStreamJobBaseUrl', 'defaultProxyJobHeartbeatSec',
        `${helpers}\n${functionSource}\nreturn fetchViaProxyJobWs;`,
    )(page, Socket, fetch, { protocol: 'https:', host: 'qa.invalid' },
        async () => 'fake-auth', () => '', 15);
    const controller = new AbortController();
    const response = run('http://fake-llm/', {
        method: 'POST', body: new Uint8Array(), signal: controller.signal,
    });
    const append = event => {
        const sequenced = { ...event, sequence: events.length + 1 };
        events.push(sequenced);
        for (const socket of sockets) socket.deliver(sequenced);
        return sequenced;
    };
    return {
        page, sockets, requests, response, controller, releaseCreation, append,
        headers: () => append({ type: 'upstream_headers', status: 200, headers: {} }),
        chunk: text => append({ type: 'chunk', dataBase64: Buffer.from(text).toString('base64') }),
        done: () => append({ type: 'done' }),
        get rejectedConnections() { return rejectedConnections; },
        assertOneGeneration() {
            assert.equal(requests.filter(r => r.method === 'POST').length, 1);
            assert.equal(requests.filter(r => r.method === 'DELETE').length, 0);
            assert.equal(rejectedConnections, 0, 'must not open a socket while the page is frozen');
        },
    };
}

test('send then freeze before headers: completed response is delivered once after resume', async () => {
    const f = fixture();
    await tick();
    f.page.hide();
    f.page.freeze();
    f.headers();
    f.chunk('reasoning\n');
    f.chunk('완료된 본문 🌼\n');
    f.done();
    f.page.showBeforeResume();
    assert.equal(f.rejectedConnections, 0);
    f.page.resume();
    const response = await f.response;
    assert.equal(response.status, 200);
    assert.equal(await response.text(), 'reasoning\n완료된 본문 🌼\n');
    f.assertOneGeneration();
});

test('freeze during reasoning: retained Response receives the complete body, without duplicate bytes', async () => {
    const f = fixture();
    await tick();
    f.headers();
    const response = await f.response;
    const output = response.text();
    const previous = f.chunk('reasoning\n');
    f.page.hide();
    f.page.freeze();
    f.chunk('본문 첫 문장.\n');
    f.page.showBeforeResume();
    f.page.resume();
    await tick();
    f.sockets.at(-1).deliver(previous);
    f.chunk('본문 마지막 문장.\n');
    f.done();
    assert.equal(await output, 'reasoning\n본문 첫 문장.\n본문 마지막 문장.\n');
    assert.equal(new URL(f.sockets.at(-1).url).searchParams.get('after'), '2');
    f.assertOneGeneration();
});

test('visible before a later resume task does not open a frozen socket', async () => {
    const f = fixture();
    await tick();
    f.page.hide();
    f.page.freeze();
    f.headers();
    f.chunk('completed while hidden');
    f.done();
    f.page.showBeforeResume();
    await tick();
    assert.equal(f.sockets.length, 1);
    assert.equal(f.rejectedConnections, 0);
    f.page.resume();
    assert.equal(await (await f.response).text(), 'completed while hidden');
    f.assertOneGeneration();
});

test('job creation completes while hidden: no socket until the page resumes', async () => {
    const f = fixture({ delayCreation: true });
    await tick();
    f.page.hide();
    f.page.freeze();
    f.releaseCreation();
    await tick();
    assert.equal(f.sockets.length, 0);
    f.headers();
    f.chunk('buffered');
    f.done();
    f.page.showBeforeResume();
    f.page.resume();
    assert.equal(await (await f.response).text(), 'buffered');
    f.assertOneGeneration();
});

test('rapid visibility/resume changes create one subscriber and clean up after completion', async () => {
    const f = fixture();
    await tick();
    f.headers();
    const output = (await f.response).text();
    f.chunk('a');
    for (let i = 0; i < 4; i++) {
        f.page.hide();
        f.page.showBeforeResume();
        f.page.resume();
    }
    await tick();
    assert.equal(f.sockets.filter(s => s.readyState === 1).length, 1);
    f.chunk('b');
    f.done();
    assert.equal(await output, 'ab');
    const count = f.sockets.length;
    f.page.hide();
    f.page.freeze();
    f.page.showBeforeResume();
    f.page.resume();
    await tick();
    assert.equal(f.sockets.length, count);
    f.assertOneGeneration();
});

test('ordinary visible connection failure does not delete the server job or retry', async () => {
    const f = fixture();
    await tick();
    f.sockets.at(-1).close();
    const response = await f.response;
    assert.equal(response.status, 502);
    await response.text();
    await tick();
    assert.equal(f.sockets.length, 1);
    f.assertOneGeneration();
});

test('explicit abort while frozen deletes the job and never reconnects', async () => {
    const f = fixture();
    await tick();
    f.page.hide();
    f.page.freeze();
    f.controller.abort();
    assert.equal((await f.response).status, 499);
    f.page.showBeforeResume();
    f.page.resume();
    await tick();
    assert.equal(f.requests.filter(r => r.method === 'DELETE').length, 1);
    assert.equal(f.sockets.length, 1);
});

test('explicit stream cancellation still cancels the server job', async () => {
    const f = fixture();
    await tick();
    f.headers();
    await (await f.response).body.cancel();
    assert.equal(f.requests.filter(r => r.method === 'DELETE').length, 1);
});
