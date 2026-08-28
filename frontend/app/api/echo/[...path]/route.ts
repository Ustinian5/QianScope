const READ_PATHS = [
  /^\/health$/,
  /^\/v1\/predictions$/,
  /^\/v1\/predictions\/[a-zA-Z0-9_-]+(?:\/(replay|export))?$/,
  /^\/v1\/insights\/[a-zA-Z0-9_-]+$/,
  /^\/v1\/personas$/,
  /^\/v1\/personas\/[a-zA-Z0-9_-]+$/,
  /^\/v1\/jobs\/[a-zA-Z0-9_-]+(?:\/result)?$/,
  /^\/v1\/populations\/[a-zA-Z0-9_-]+$/,
  /^\/v1\/questionnaires\/[a-zA-Z0-9_-]+$/,
  /^\/v1\/population-margins\/[a-zA-Z0-9_-]+$/,
  /^\/v1\/calibration-datasets\/[a-zA-Z0-9_-]+$/,
  /^\/v1\/calibrations\/[a-zA-Z0-9_-]+$/,
  /^\/v1\/examples\/(population-margin|calibration-dataset)$/,
  /^\/v1\/social-world\/preset$/,
  /^\/v1\/social-world\/simulations\/[a-zA-Z0-9_-]+(?:\/replay)?$/,
  /^\/v1\/social-world\/simulations\/[a-zA-Z0-9_-]+\/agents(?:\/[a-zA-Z0-9_-]+)?$/,
  /^\/v1\/social-world\/simulations\/[a-zA-Z0-9_-]+\/locations\/[a-zA-Z0-9_-]+$/,
  /^\/v1\/social-world\/simulations\/[a-zA-Z0-9_-]+\/snapshots\/\d+\/\d+$/,
  /^\/v1\/cities\/suzhou$/,
  /^\/v1\/city-simulations\/[a-zA-Z0-9_-]+\/(results|replay|report)$/,
  /^\/v1\/event-forecasts\/[a-zA-Z0-9_-]+\/(results|replay)$/,
  /^\/v1\/models(?:\/[a-zA-Z0-9_-]+\/card)?$/,
  /^\/v1\/simulations\/[a-zA-Z0-9_-]+(?:\/(results|trajectory|replay))?$/,
];

const WRITE_PATHS = [
  /^\/v1\/populations\/generate$/,
  /^\/v1\/questionnaires$/,
  /^\/v1\/population-margins$/,
  /^\/v1\/calibration-datasets$/,
  /^\/v1\/calibrations$/,
  /^\/v1\/predictions$/,
  /^\/v1\/insights$/,
  /^\/v1\/personas\/[a-zA-Z0-9_-]+\/interview$/,
  /^\/v1\/jobs\/(insight|prediction|world)$/,
  /^\/v1\/jobs\/[a-zA-Z0-9_-]+\/cancel$/,
  /^\/v1\/social-world\/simulations$/,
  /^\/v1\/predictions\/[a-zA-Z0-9_-]+\/outcomes$/,
  /^\/v1\/event-forecasts$/,
  /^\/v1\/event-forecasts\/compile$/,
  /^\/v1\/event-forecasts\/backtest$/,
  /^\/v1\/cities\/suzhou\/simulate$/,
  /^\/v1\/cities\/suzhou\/compile$/,
  /^\/v1\/questionnaires\/predict$/,
];

type Context = { params: Promise<{ path: string[] }> | { path: string[] } };

function backendUrl(path: string) {
  const configured = process.env.ECHO_API_URL
    || (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000' : '');
  if (!configured) {
    throw new Error('ECHO_API_URL is not configured for this deployment.');
  }
  return `${configured.replace(/\/$/, '')}${path}`;
}

async function proxy(request: Request, context: Context) {
  const params = await context.params;
  const path = `/${params.path.join('/')}`;
  const allowed = request.method === 'GET'
    ? READ_PATHS.some((pattern) => pattern.test(path))
    : request.method === 'POST' && WRITE_PATHS.some((pattern) => pattern.test(path));

  if (!allowed) {
    return Response.json({ detail: 'This API path is not exposed by the frontend gateway.' }, { status: 404 });
  }

  try {
    const body = request.method === 'GET' ? undefined : await request.text();
    const query = new URL(request.url).search;
    const upstream = await fetch(backendUrl(`${path}${query}`), {
      method: request.method,
      body,
      headers: body ? { 'content-type': request.headers.get('content-type') || 'application/json' } : undefined,
      cache: 'no-store',
      signal: AbortSignal.timeout(300_000),
    });
    const headers = new Headers({
      'cache-control': 'no-store',
      'content-type': upstream.headers.get('content-type') || 'application/json',
    });
    const disposition = upstream.headers.get('content-disposition');
    const requestId = upstream.headers.get('x-request-id');
    if (disposition) headers.set('content-disposition', disposition);
    if (requestId) headers.set('x-request-id', requestId);
    return new Response(upstream.body, { status: upstream.status, headers });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown backend error';
    return Response.json(
      {
        detail: 'ECHO-SWM backend is unavailable.',
        hint: 'Start the FastAPI service or configure ECHO_API_URL.',
        cause: message,
      },
      { status: 503 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
