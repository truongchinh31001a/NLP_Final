from __future__ import annotations


TRAIN_JSONL = """{"id":"s1","session":"2001","q":"1","l1":"XX","age":"20","score":12,"combined-score":24,"score-old-scale":"B","text":"She go school.","edits":[[0,[[4,6,"goes","AGV"],[7,7,"to","MP(UT)"]]]]}
"""

TRAIN_XML = """<train>
  <script id="s1" session="2001">
    <learner l1="XX" age="20" />
    <results><s>12</s></results>
    <answer q="1">
      <eval />
      <text>She <e type="AGV"><i>go</i><c>goes</c></e> <e type="MP"><i></i><c>to</c><e type="UT"><i></i><c>to</c></e></e> school.</text>
    </answer>
  </script>
</train>
"""

