import { strict as assert } from "assert";
import { createUserValidator } from "../src/componentFactories";
import { SpecializedProcessor } from "../src/SpecializedProcessor";
import type { ProcessResult, RecordTransformer, UserRecord } from "../src/types";

const processor = new SpecializedProcessor({ label: "main", multiplier: 2 });
const result = processor.process({ id: "a", value: 4, tags: ["x"] });

assert.equal(result.valid, true);
assert.equal(result.notes.includes("specialized"), true);
assert.equal(result.transformed.enriched, true);

const user: UserRecord = { id: "u1", score: 10, active: true };
const userValidator = createUserValidator();
const userTransformer: RecordTransformer<UserRecord> = (input) => ({
  id: input.id,
  score: input.score + 1,
  active: input.active,
});
const userResult: ProcessResult<UserRecord> = {
  input: user,
  valid: userValidator(user),
  transformed: userTransformer(user),
  notes: ["user"],
};

assert.equal(userResult.valid, true);
assert.equal(userResult.transformed.score, 11);
