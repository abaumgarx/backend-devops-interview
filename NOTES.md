# Notes
I decided to focus on developer experience and blog/api endpoint refactoring. Some security concerns have been fixed too. In detail:

- Developer experience: Docker compose has been added.
- Developer experience: Database (DB) seeding performance has been improved.
- Performance improvements DB: Use a persistent connection (set timeout).
- Performance improvements blog/api: Introduced cursor based paging.
- Performance improvements blog/api: Fixed N+1 database calls.
- Other improvements blog/api: Ditch the manual serialization, since the schema specifies that anyways.
- Other improvements blog/api: Use an atomic F() expression to increment view_count (concurrency concern).
- Other improvements blog/api: Make create_post atomic (DB consistency concern).
- Security concerns: DB credentials are now obtained from environment variables (using dj_database_url)
- Security concerns: Length ceiling - unbounded storage/DoS vector has been fixed (introducing max_length for title and body).

## Disclaimer:
- AI has been used. The main conversation transcript (transcript.txt) can be found in the repository.
- The sub conversation about improving the DB seeding was not linear. A separate chat has been used - reverting and trying again until reaching the final result.

## What I didn't do:
- Production deployment preparation (CI) has been left aside intentionally.
- DB schema related improvements, like indices or full text search.

## What I would do next:
- Figure out more about the goals - talk with someone about the goals.
- DB related fixes. E.g., icontains results in a full table scan (search backend).
- Talk with someone who has more experience with CI.
- Fix security concerns by environment driven settings (DEBUG=False, SECURE_*).
- Tackle the user authentication (if the Non-goals section would be lifted).
