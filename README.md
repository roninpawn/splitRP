# SplitRP
Automated Video Analysis Tool for Speedrun Moderation 
*(RTA and IGT timing supported)*

## Video Analyzer
This branch deprecates live autosplitting and focuses entirely on video analysis.

- **SplitRP automates timing** speedruns by analyzing the video submitted by a speedrunner.
    - It looks through each frame of an .mp4 file *(or other supported video format)*, and compares
	    what it sees to a set of stored images. Those images represent the points in the run when a
	    split *(or other timing action)* should occur.
	 - With a well-written pattern-file, and a good collection of test images, SplitRP is capable
	    of analyzing speedruns for **both RTA and IGT timing** -- removing time spent on
	    load-screens, and making official timing more fair to players running on slower machines.
	 - It can even be used to help moderation **detect fake / spliced runs!** Drawing moderators'
	    attention to sections of the video where certain frames pop up when they definitely 
	    shouldn't!


      - SplitRP now uses Multiprocessing to conduct video anaylsis.
         : 3x faster than any previous build.
         : Consumes only about 1.5Gb's while processing 1080p video.
         : Processes ~4.5 seconds of 1080p/60fps video per second.
         : Processes ~8.5 seconds of 1080p/30fps video per second.
         : Processes ~12.5 seconds of 720p/60fps video per second.
         : Processes ~15.5 seconds of 720p/30fps video per second.
	    
- The way this works is, a moderator or runner of a game creates a SplitRP pattern file to use
	  as a sort of roadmap for timing runs of that game. Images of split-frames are placed in a
	  directory, and the pattern file is told how close a match it should require to trigger a
	  split. SplitRP then uses this roadmap to parse over each individual frame in the recording,
	  seeing if that frame is a match. **It's as simple as that!***
	
    - ***But it's not as simple as that!** SplitRP's pattern files can be built to support IGT timing by
	  triggering 'pause' events that will discard any time spent on a load screen, or navigating
	  menus before or during a run. Give SplitRP an image of the frame on which to start the run,
	  an image of when a split should occur, and an image of what a load screen looks like -- and
	  you can write a pattern file that will start the run, immediately pause timing until loading
	  ends, then drop into a cycle where it continuously looks for splits. Run a video file through
	  SplitRP with that setup and it will simultaneously generate a list of both RTA and IGT splits,
	  summing up their totals and handing you all the results.

- Though very much a work in process, SplitRP has been helping run moderation on the Clustertruck
  leaderboards for quite some time already. Without this tool, conversion of those boards to IGT
  simply would not have been feasible. And without conversion to IGT, our leaderboards (yay! I'm a
  moderator now) would have been forced to remain pay-to-win -- where the runner with the beefiest
  PC has a thirty-second advantage.

### Try SplitRP Today!*
**No warranties stated or implied. Use at your own risk. Choking hazard for children under 3.
Allow 8 to 12 weeks shipping and handling. Action jetpack sold seperately.*