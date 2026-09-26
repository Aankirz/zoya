import { handle, type Env } from "./relay";
import { neonStore } from "./store";

export default {
  fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    return handle(request, env, neonStore(env.RELAY_DATABASE_URL), (promise) => ctx.waitUntil(promise));
  },
} satisfies ExportedHandler<Env>;
