Emotions for HN
================


It is a tini-tiny experiment to see whether people will have an impact if their comment is flagged as having some form of positive or negative emotional effect on others on hackernews. It can also be used to avoid certain comments if you are not interested in seeing those comments.

Emotions for HN is a chrome plugin I wrote over a weekend, which adds a UI control to each comment showing 5 emotions (listed below). Anybody can vote on these emotions and each comment will show how much emotions it accumulated. Supported emotions:

- Empathetic
- Encouraging
- Ad Hominem
- Flame war
- Discouraging

The emotion having the highest vote on certain comment labeled as an emotion of that comment. So e.g. certain comment has a large number of vote for 'Empathetic' then the comment is labeled as empathetic. You can also enable emotion-highlighting where you can see all the comments which are labeled with given emotion. See below screenshot. 


Server
=======

This app is designed to host on Google App Engine. No fancy configuration is needed to host your own version.
Just change the `HN_EMOTIONS_BASE_URL` present at the top of the `main.py` to match your host.

Client
======

Browser plugin is written keeping both Chrome and Firefox browsers in mind. It doesn't use any browser specific
feature and same code runs perfectly fine on both of the browsers. Like server you just need to change
 `HN_EMOTIONS_URL` at the top of the `content.js` to point to your own server.
 

Licence
=======
Code released under the Apache License.